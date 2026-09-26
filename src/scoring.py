import sqlite3
from collections import defaultdict

class ScoringEngine:
    def __init__(self, w1=1.0, w2=1.0):
        # Default weights. Plan states uniform starting assumption.
        self.w1 = w1
        self.w2 = w2

    def calculate_clause_score(self, severity, specificity):
        """
        Calculates the deterministic risk score for a single clause.
        Formula: (w1 * severity) + (w2 * specificity)
        """
        sev = float(severity) if severity is not None else 0.0
        spec = float(specificity) if specificity is not None else 0.0
        return (self.w1 * sev) + (self.w2 * spec)

    def calculate_service_score_from_clauses(self, clauses):
        """
        Calculates the normalized individual privacy exposure of one service.

        Each clause contributes:
            severity × specificity

        The service score is the mean clause depth, so the result is
        independent of policy length.

        Since severity and specificity are each scored from 1 to 5,
        the resulting score is between 1 and 25.
        """
        if not clauses:
            return 0.0

        clause_depths = []

        for clause in clauses:
            severity = float(clause.get("severity_score") or 0.0)
            specificity = float(clause.get("specificity_score") or 0.0)

            clause_depths.append(severity * specificity)

        return sum(clause_depths) / len(clause_depths)

    def _entity_mention_rows(self, cursor):
        """(canonical_entity_name, service_id, severity_score, specificity_score) for every mention."""
        cursor.execute("""
            SELECT ce.name, c.service_id, c.severity_score, c.specificity_score
            FROM canonical_entities ce
            JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
            JOIN clauses c ON cem.clause_id = c.id
        """)
        return cursor.fetchall()

    def compute_composite_portfolio_score(self, cursor):
        """
        The REAL entity-aware composite score, matching the project's stated
        novelty claim: breadth (category coverage) + concentration-weighted
        entity exposure — not just a flat sum of per-clause scores.

        concentration(e) = raw count of DISTINCT services mentioning entity e
        depth(e) = mean(severity_score * specificity_score) across e's mentions
        entity_exposure(e) = concentration(e) * depth(e)
        portfolio_score = sum(entity_exposure(e) for all e)   -- cumulative, not averaged

        This is deliberately a raw-count/cumulative design, not a fraction
        normalized by total_services: a fraction would shrink for every
        existing entity whenever the portfolio grows, even entities the new
        service never touches, which incorrectly makes existing risk look
        smaller just because something unrelated was added.

        Returns (portfolio_score, breakdown_dict).
        """
        rows = self._entity_mention_rows(cursor)

        concentration = defaultdict(set)   # entity -> set of service_ids
        depths = defaultdict(list)         # entity -> list of per-mention depth values
        for name, service_id, severity, specificity in rows:
            concentration[name].add(service_id)
            sev = float(severity) if severity is not None else 0.0
            spec = float(specificity) if specificity is not None else 0.0
            depths[name].append(sev * spec)

        entity_exposure = {}
        for name in set(concentration) | set(depths):
            conc = len(concentration.get(name, set()))
            dep_list = depths.get(name, [])
            mean_depth = sum(dep_list) / len(dep_list) if dep_list else 0.0
            entity_exposure[name] = conc * mean_depth

        portfolio_score = sum(entity_exposure.values())

        # Breadth: fraction of services touching each risk_category (diagnostic only,
        # not blended into the primary score, same reasoning as the entity_exposure
        # design above — reported separately so it isn't silently double counted).
        cursor.execute("SELECT COUNT(*) FROM services")
        total_services = cursor.fetchone()[0] or 1
        cursor.execute("SELECT DISTINCT service_id, risk_category FROM clauses")
        category_services = defaultdict(set)
        for service_id, risk_category in cursor.fetchall():
            if not risk_category:
                continue
            category_services[risk_category].add(service_id)
        breadth = {cat: len(svcs) / total_services for cat, svcs in category_services.items()}

        breakdown = {
            "entity_exposure": entity_exposure,
            "concentration_by_entity": {name: len(s) for name, s in concentration.items()},
            "depth_by_entity": {
                name: (sum(v) / len(v) if v else 0.0) for name, v in depths.items()
            },
            "breadth_by_category": breadth,
        }
        return portfolio_score, breakdown

    def get_portfolio_data(self, db_path):
        """
        Extracts the portfolio structure and calculates the REAL composite
        (entity-aware, concentration-weighted) portfolio score.
        Returns a structured dictionary of the portfolio. Same shape as
        before (portfolio_score, services, all_canonical_entities) so
        dashboard.py and the extension don't need to change, plus an added
        "breakdown" key with the entity-level detail for anyone who wants it.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM services")
        services = cursor.fetchall()

        portfolio_score, breakdown = self.compute_composite_portfolio_score(cursor)

        service_details = []
        portfolio_entities = set()
        for service_id, service_name in services:
            cursor.execute(
                "SELECT id, severity_score, specificity_score FROM clauses WHERE service_id = ?",
                (service_id,),
            )
            clauses = cursor.fetchall()
            clause_dicts = [{'severity_score': c[1], 'specificity_score': c[2]} for c in clauses]

            # Normalized individual service exposure score.
            # This is separate from the cumulative portfolio score.
            svc_flat_score = self.calculate_service_score_from_clauses(clause_dicts)

            cursor.execute("""
                SELECT ce.name
                FROM canonical_entities ce
                JOIN clause_entity_mapping cem ON ce.id = cem.entity_id
                JOIN clauses c ON cem.clause_id = c.id
                WHERE c.service_id = ?
            """, (service_id,))
            entities = {row[0] for row in cursor.fetchall()}
            portfolio_entities.update(entities)

            service_details.append({
                "service_name": service_name,
                "service_score": svc_flat_score,
                "entities": list(entities)
            })

        conn.close()

        return {
            "portfolio_score": portfolio_score,
            "services": service_details,
            "all_canonical_entities": list(portfolio_entities),
            "breakdown": breakdown,
        }
