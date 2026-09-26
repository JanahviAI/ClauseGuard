import os
import shutil
import tempfile
try:
    from .scoring import ScoringEngine
    from .canonicalize import EntityCanonicalizer, DatabaseLoader
    from .db import init_db
except ImportError:
    from scoring import ScoringEngine
    from canonicalize import EntityCanonicalizer, DatabaseLoader
    from db import init_db

class MarginalRiskEngine:
    def __init__(self, db_path, w1=1.0, w2=1.0):
        self.db_path = db_path
        self.scoring_engine = ScoringEngine(w1, w2)
        self.canonicalizer = EntityCanonicalizer()

    def calculate_marginal_risk(self, candidate_json):
        """
        Determines the additional risk introduced by adding a candidate service,
        using DIRECT RECOMPUTATION: ΔR(s|P) = R(P ∪ {s}) - R(P), computed on the
        REAL composite (entity-aware, concentration-weighted) score — not a
        shortcut formula. This is deliberate (see project plan, C5): a direct
        before/after diff avoids the correctness risk of trying to derive a
        closed-form incremental update to the concentration term.

        Because concentration is part of the score, an overlapping entity's
        marginal contribution is NOT simply "add the candidate's own score" —
        it reflects how that entity's concentration/depth shifts once it's
        confirmed across an additional service. This replaces the previous
        version, which set marginal_risk_delta = candidate_score unconditionally
        regardless of overlap (a known, now-fixed limitation).

        Never mutates the real database: all candidate-inclusive computation
        happens on a throwaway temp-file copy that is deleted afterward.
        """
        candidate_name = candidate_json.get("service_name", "Unknown Candidate")
        candidate_clauses = candidate_json.get("clauses", [])

        # 1. Baseline: composite score of the real portfolio, untouched.
        if os.path.exists(self.db_path):
            import sqlite3
            baseline_conn = sqlite3.connect(self.db_path)
            baseline_cursor = baseline_conn.cursor()
            baseline_score, _ = self.scoring_engine.compute_composite_portfolio_score(baseline_cursor)
            baseline_cursor.execute("""
                SELECT DISTINCT ce.name
                FROM canonical_entities ce
                JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
            """)
            existing_entities = {row[0] for row in baseline_cursor.fetchall()}
            baseline_conn.close()
        else:
            baseline_score = 0.0
            existing_entities = set()

        # Candidate's own standalone score, kept for display/reference only —
        # NOT used as the marginal delta (see docstring above).
        candidate_score = self.scoring_engine.calculate_service_score_from_clauses(candidate_clauses)

        # Candidate's canonicalized entities, computed the same way the DB load
        # will do it, so overlap detection matches what actually gets stored.
        candidate_entities = set()
        for clause in candidate_clauses:
            for raw_entity in clause.get("entities", []):
                candidate_entities.add(self.canonicalizer.canonicalize(raw_entity))

        overlapping_entities = candidate_entities.intersection(existing_entities)
        new_entities = candidate_entities.difference(existing_entities)

        # 2. R(P ∪ {s}): copy the real DB (or init a fresh one if none exists yet)
        #    to a temp file, load the candidate into the COPY, recompute composite
        #    score there. The temp file is always removed, real DB never touched.
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(tmp_fd)
        try:
            if os.path.exists(self.db_path):
                shutil.copyfile(self.db_path, tmp_path)
            else:
                init_db(tmp_path)

            loader = DatabaseLoader(tmp_path)
            loader.load_extraction(candidate_json, self.canonicalizer)

            import sqlite3
            combined_conn = sqlite3.connect(tmp_path)
            combined_cursor = combined_conn.cursor()
            new_portfolio_score, _ = self.scoring_engine.compute_composite_portfolio_score(combined_cursor)
            combined_conn.close()
        finally:
            os.remove(tmp_path)

        marginal_risk_delta = new_portfolio_score - baseline_score

        return {
            "candidate_name": candidate_name,
            "baseline_portfolio_risk": baseline_score,
            "candidate_service_risk": candidate_score,
            "new_portfolio_risk": new_portfolio_score,
            "marginal_risk_delta": marginal_risk_delta,
            "overlapping_entities": list(overlapping_entities),
            "newly_introduced_entities": list(new_entities)
        }

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python marginal.py <path_to_candidate.json>")
        sys.exit(1)

    candidate_path = sys.argv[1]
    with open(candidate_path, 'r', encoding='utf-8') as f:
        candidate_data = json.load(f)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_file_path = os.path.join(base_dir, 'data', 'db', 'portfolio.db')

    engine = MarginalRiskEngine(db_file_path)
    result = engine.calculate_marginal_risk(candidate_data)

    print(json.dumps(result, indent=2))
