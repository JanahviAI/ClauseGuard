import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import numpy as np

class PrivacyPrefilter:
    def __init__(self, uncertainty_margin=0.15):
        self.vectorizer = TfidfVectorizer()
        self.classifier = LogisticRegression(random_state=42)
        self.is_trained = False
        self.uncertainty_margin = float(uncertainty_margin)
        
    def train(self, texts, labels):
        """
        Train the prefilter with a small labelled dataset.
        labels: 1 for privacy-relevant, 0 for not privacy-relevant.
        """
        X = self.vectorizer.fit_transform(texts)
        self.classifier.fit(X, labels)
        self.is_trained = True

    def train_with_minimal_fixture(self):
        """
        Loads a minimal hardcoded training set for baseline initialization.
        """
        texts = [
            "We share your location data with marketing partners.",
            "You can opt out of data sharing in your account settings.",
            "We collect cookies to improve site performance.",
            "Click here to reset your password.",
            "The app requires an internet connection to stream music.",
            "Welcome to the user manual.",
            "Your IP address is logged for security purposes.",
            "Contact customer support if the app crashes."
        ]
        labels = [1, 1, 1, 0, 0, 0, 1, 0]
        self.train(texts, labels)

    def filter_candidates(self, clauses):
        """
        Filters a list of clauses, returning only those predicted as privacy-relevant.
        """
        scored = self.score_candidates(clauses)
        return [
            item["clause"]
            for item in scored
            if item["is_privacy"] or item["is_uncertain"]
        ]

    def score_candidates(self, clauses):
        """
        Scores clauses with deterministic LR probabilities.
        Returns items with predicted class and uncertainty flag.
        """
        if not self.is_trained:
            self.train_with_minimal_fixture()

        if not clauses:
            return []

        X = self.vectorizer.transform(clauses)
        probabilities = self.classifier.predict_proba(X)[:, 1]
        predictions = self.classifier.predict(X)

        results = []
        for clause, pred, prob in zip(clauses, predictions, probabilities):
            prob = float(prob)
            results.append(
                {
                    "clause": clause,
                    "is_privacy": bool(pred == 1),
                    "privacy_probability": prob,
                    "is_uncertain": abs(prob - 0.5) <= self.uncertainty_margin,
                }
            )

        return results
