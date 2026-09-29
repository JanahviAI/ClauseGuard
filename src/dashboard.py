import os
import sys
import logging
import json
import sqlite3
from flask import Flask, request, jsonify, send_from_directory

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scoring import ScoringEngine
from src.marginal import MarginalRiskEngine
from src.extract import extract_pipeline
from src.canonicalize import EntityCanonicalizer
from src.config import get_provider, get_model

app = Flask(__name__, static_folder='static')

def _internal_server_error(public_message, exc):
    logging.exception(public_message, exc_info=exc)
    return jsonify({"error": public_message}), 500

# Minimal CORS for extension development
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'db', 'portfolio.db'))

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    engine = ScoringEngine()
    try:
        data = engine.get_portfolio_data(DB_PATH)
        concentration = data.get("breakdown", {}).get("concentration_by_entity", {})
        repeated = [
            {"entity": name, "service_count": count}
            for name, count in concentration.items()
            if count > 1
        ]
        repeated.sort(key=lambda item: item["service_count"], reverse=True)
        data["repeated_entities"] = repeated
        return jsonify(data)
    except Exception as e:
        return _internal_server_error("Failed to load portfolio data.", e)

@app.route('/api/marginal-risk', methods=['POST'])
def calculate_marginal_risk():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    candidate = request.json
    if not candidate or 'service_name' not in candidate or 'clauses' not in candidate:
        return jsonify({"error": "Invalid candidate JSON structure"}), 400
        
    engine = MarginalRiskEngine(DB_PATH)
    try:
        result = engine.calculate_marginal_risk(candidate)
        return jsonify(result)
    except Exception as e:
        return _internal_server_error("Failed to calculate marginal risk.", e)

@app.route('/api/analyze-policy', methods=['POST', 'OPTIONS'])
def analyze_policy():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    data = request.json
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' in request body"}), 400
        
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Policy text is empty"}), 400
        
    url = data.get("url", "")
    title = data.get("title", "")
    policy_detected = bool(data.get("policy_detected", False))
    
    # Simple service name extraction fallback
    service_name = title.split('-')[0].strip() if title else ""
    if not service_name and url:
        # Very naive fallback from URL
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        service_name = parsed.netloc.replace('www.', '').split('.')[0].capitalize()
        
    if not service_name:
        service_name = "Unknown Web Service"

    try:
        # C1 Extraction
        extracted = extract_pipeline(text, service_name)
        
        # C2 Canonicalization (in-memory)
        canonicalizer = EntityCanonicalizer()
        all_canonical_entities = set()
        for clause in extracted.get("clauses", []):
            canon_list = [canonicalizer.canonicalize(e) for e in clause.get("entities", [])]
            clause["canonical_entities"] = canon_list
            all_canonical_entities.update(canon_list)
            
        # C4 Scoring
        scoring_engine = ScoringEngine()
        risk = scoring_engine.calculate_service_score_from_clauses(extracted.get("clauses", []))
        
        provider = get_provider()
        mode = provider.upper()
        
        # Assemble Response
        response_data = {
            "service_name": extracted.get("service_name"),
            "mode": mode,
            "model": get_model(provider),
            "provider": provider,
            "clauses": extracted.get("clauses", []),
            "canonical_entities": sorted(list(all_canonical_entities)),
            "risk": risk,
            "policy_url": url,
            "policy_detected": policy_detected,
        }
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        return _internal_server_error("Extraction failed.", e)

@app.route('/api/submit-policy', methods=['POST'])
def submit_policy():
    payload = request.json or {}
    if "service_name" not in payload or "clauses" not in payload:
        return jsonify({"error": "Payload must include service_name and clauses"}), 400

    try:
        from src.db import init_db
        from src.canonicalize import DatabaseLoader
    except ImportError:
        from db import init_db
        from canonicalize import DatabaseLoader

    try:
        init_db(DB_PATH)
        canonicalizer = EntityCanonicalizer()
        loader = DatabaseLoader(DB_PATH)
        loader.load_extraction(payload, canonicalizer)
        return jsonify({
            "status": "stored",
            "service_name": payload.get("service_name"),
            "clauses_loaded": len(payload.get("clauses", [])),
        })
    except Exception as e:
        return _internal_server_error("Failed to store policy in portfolio.", e)

@app.route('/api/service/<service_name>', methods=['GET'])
def get_service_detail(service_name):
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, category FROM services WHERE name = ?", (service_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Service not found"}), 404

    service_id = row["id"]
    cursor.execute(
        """
        SELECT id, text, severity_score, specificity_score, risk_category,
               recipients_json, entity_specificity, retention_raw,
               retention_days, purposes_json, confidence, evidence
        FROM clauses
        WHERE service_id = ?
        """,
        (service_id,),
    )
    clause_rows = cursor.fetchall()

    clause_payload = []
    for clause in clause_rows:
        clause_id = clause["id"]
        cursor.execute(
            """
            SELECT ce.name
            FROM canonical_entities ce
            JOIN clause_entity_mapping cem ON cem.entity_id = ce.id
            WHERE cem.clause_id = ?
            """,
            (clause_id,),
        )
        entities = [entity_row[0] for entity_row in cursor.fetchall()]

        clause_payload.append({
            "text": clause["text"],
            "severity_score": clause["severity_score"],
            "specificity_score": clause["specificity_score"],
            "risk_category": clause["risk_category"],
            "entities": entities,
            "recipients": json.loads(clause["recipients_json"] or "[]"),
            "entity_specificity": clause["entity_specificity"],
            "retention": {
                "raw_text": clause["retention_raw"] or "",
                "duration_days": clause["retention_days"],
            },
            "purposes": json.loads(clause["purposes_json"] or "[]"),
            "confidence": clause["confidence"],
            "evidence": clause["evidence"] or "",
        })

    conn.close()

    return jsonify({
        "service_name": row["name"],
        "category": row["category"],
        "clauses": clause_payload,
    })

@app.route('/api/overlap-graph', methods=['GET'])
def get_overlap_graph():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    engine = ScoringEngine()
    try:
        data = engine.get_portfolio_data(DB_PATH)
        
        nodes = []
        edges = []
        
        # Add service nodes
        for service in data.get("services", []):
            nodes.append({"id": service["service_name"], "group": "service"})
            
        # Add entity nodes and edges
        added_entities = set()
        for service in data.get("services", []):
            s_name = service["service_name"]
            for ent in service.get("entities", []):
                if ent not in added_entities:
                    nodes.append({"id": ent, "group": "entity"})
                    added_entities.add(ent)
                # Deduplicate edges conceptually
                edge_id = f"{s_name}->{ent}"
                edges.append({"source": s_name, "target": ent, "id": edge_id})
        
        # Deduplicate edges list
        unique_edges = {e["id"]: e for e in edges}.values()
        
        return jsonify({
            "nodes": nodes,
            "edges": list(unique_edges)
        })
    except Exception as e:
        return _internal_server_error("Failed to load overlap graph data.", e)

@app.route('/api/compare-services', methods=['POST'])
def compare_services():
    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Portfolio database not found"}), 404
        
    req_data = request.json
    if not req_data or 'candidate_a' not in req_data or 'candidate_b' not in req_data:
        return jsonify({"error": "Must provide candidate_a and candidate_b"}), 400
        
    engine = MarginalRiskEngine(DB_PATH)
    try:
        res_a = engine.calculate_marginal_risk(req_data["candidate_a"])
        res_b = engine.calculate_marginal_risk(req_data["candidate_b"])
        return jsonify({
            "candidate_a": res_a,
            "candidate_b": res_b
        })
    except Exception as e:
        return _internal_server_error("Failed to compare candidate services.", e)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    print("Starting ClauseGuard Dashboard...")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host='127.0.0.1', port=5000, debug=True)
