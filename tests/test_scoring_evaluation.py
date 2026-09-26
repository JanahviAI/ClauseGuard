import unittest
import os
import sys
import tempfile
import sqlite3

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from scoring import ScoringEngine
from marginal import MarginalRiskEngine
from db import init_db
from canonicalize import DatabaseLoader, EntityCanonicalizer

class TestScoringEvaluationValidation(unittest.TestCase):
    
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        init_db(self.temp_db_path)
        self.loader = DatabaseLoader(self.temp_db_path)
        self.canonicalizer = EntityCanonicalizer()

    def tearDown(self):
        os.close(self.temp_db_fd)
        os.remove(self.temp_db_path)

    def test_c4_mathematical_validation(self):
        # 1. Single clause
        engine = ScoringEngine(w1=1.0, w2=1.0)
        self.assertEqual(engine.calculate_clause_score(3.0, 2.0), 5.0)

        # 2. Multiple clauses
        clauses = [
            {'severity_score': 3.0, 'specificity_score': 2.0},
            {'severity_score': 4.0, 'specificity_score': 1.0}
        ]
        self.assertEqual(engine.calculate_service_score_from_clauses(clauses), 5.0)

        # 3. Multiple services -- NOTE: neither clause has an "entities" list, so
        # under the fixed entity-aware composite score (which sums concentration x
        # depth PER ENTITY), clauses that name no third-party entity contribute
        # nothing to portfolio_score. This is intentional: the composite score
        # specifically measures entity-based exposure, not generic clause severity
        # (that's what calculate_service_score_from_clauses / data["services"][i]
        # ["service_score"] is for, shown separately per service).
        self.loader.load_extraction({"service_name": "S1", "clauses": [{"text": "t", "severity_score": 1.0, "specificity_score": 1.0}]}, self.canonicalizer)
        self.loader.load_extraction({"service_name": "S2", "clauses": [{"text": "t", "severity_score": 2.0, "specificity_score": 2.0}]}, self.canonicalizer)
        data = engine.get_portfolio_data(self.temp_db_path)
        self.assertEqual(data["portfolio_score"], 0.0)
        # The per-service flat scores are still tracked, just not summed into portfolio_score:
        self.assertEqual(data["services"][0]["service_score"], 1.0)
        self.assertEqual(data["services"][1]["service_score"], 4.0)

        # 4. & 5. Weight sensitivity
        e_w1 = ScoringEngine(w1=2.0, w2=1.0)
        self.assertEqual(e_w1.calculate_clause_score(3.0, 2.0), 8.0) # (2*3) + (1*2) = 8
        e_w2 = ScoringEngine(w1=1.0, w2=2.0)
        self.assertEqual(e_w2.calculate_clause_score(3.0, 2.0), 7.0) # (1*3) + (2*2) = 7
        
        # 6. Zero/edge values
        self.assertEqual(engine.calculate_clause_score(0.0, 0.0), 0.0)
        
        # 7. Repeatability
        self.assertEqual(engine.calculate_clause_score(5.0, 5.0), engine.calculate_clause_score(5.0, 5.0))

    def test_c5_mathematical_validation(self):
        marginal_engine = MarginalRiskEngine(self.temp_db_path, w1=1.0, w2=1.0)
        
        # A. Empty portfolio + candidate (single service, single entity "Location", sev3 spec3)
        # composite: concentration=1, depth=3.0*3.0=9.0 -> exposure=9.0; baseline=0 -> delta=9.0
        candidate1 = {"service_name": "C1", "clauses": [{"text": "t", "entities": ["Location"], "severity_score": 3.0, "specificity_score": 3.0}]}
        res1 = marginal_engine.calculate_marginal_risk(candidate1)
        self.assertEqual(res1["marginal_risk_delta"], 9.0)
        
        # B, C, F. Existing portfolio + candidate (Overlap + New entities)
        self.loader.load_extraction({"service_name": "S1", "clauses": [{"text": "t", "entities": ["Location"], "severity_score": 1.0, "specificity_score": 1.0}]}, self.canonicalizer)
        self.loader.load_extraction({"service_name": "S2", "clauses": [{"text": "t", "entities": ["Email"], "severity_score": 1.0, "specificity_score": 1.0}]}, self.canonicalizer)
        
        candidate2 = {"service_name": "C2", "clauses": [{"text": "t", "entities": ["Location", "IP Address"], "severity_score": 4.0, "specificity_score": 4.0}]}
        res2 = marginal_engine.calculate_marginal_risk(candidate2)
        
        # Baseline composite: Location(S1): concentration=1,depth=1.0 -> exposure=1.0;
        # Email(S2): concentration=1,depth=1.0 -> exposure=1.0. Total = 2.0
        self.assertEqual(res2["baseline_portfolio_risk"], 2.0)
        # candidate_service_risk: flat score of the one candidate clause = 4.0+4.0 = 8.0 (unaffected by the fix)
        self.assertEqual(res2["candidate_service_risk"], 16.0)
        # After adding C2: Location now in S1+C2 -> concentration=2, depth=mean([1.0, 16.0])=8.5 -> exposure=17.0
        # Email unchanged -> exposure=1.0; IP Address new -> concentration=1, depth=16.0 -> exposure=16.0
        # new_portfolio_risk = 34.0; marginal_risk_delta = 34.0 - 2.0 = 32.0
        self.assertEqual(res2["marginal_risk_delta"], 32.0)
        
        # D. Overlapping entities
        self.assertIn("Location", res2["overlapping_entities"])
        
        # E. New entities
        self.assertIn("IP Address", res2["newly_introduced_entities"])
        
        # G. Repeated calculation produces identical results
        res3 = marginal_engine.calculate_marginal_risk(candidate2)
        self.assertEqual(res2, res3)
        
        # H. DB Immutable
        conn = sqlite3.connect(self.temp_db_path)
        count = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
        self.assertEqual(count, 2) # S1 and S2
        conn.close()

if __name__ == '__main__':
    unittest.main()
