class ValidationError(Exception):
    pass


def validate_extraction_output(data):
    if not isinstance(data, dict):
        raise ValidationError("Top-level output must be a dictionary.")
    if "service_name" not in data or not isinstance(data["service_name"], str):
        raise ValidationError("Missing or invalid 'service_name' string.")
    if "clauses" not in data or not isinstance(data["clauses"], list):
        raise ValidationError("Missing or invalid 'clauses' array.")

    for i, clause in enumerate(data["clauses"]):
        if not isinstance(clause, dict):
            raise ValidationError(f"Clause at index {i} must be a dictionary.")
        if not isinstance(clause.get("text"), str) or not clause["text"].strip():
            raise ValidationError(f"Clause at index {i} missing valid 'text' string.")
        if not isinstance(clause.get("entities"), list):
            raise ValidationError(f"Clause at index {i} missing valid 'entities' array.")
        if any(not isinstance(entity, str) or not entity.strip() for entity in clause["entities"]):
            raise ValidationError(f"Clause at index {i} contains an invalid entity.")

        for field in ("severity_score", "specificity_score"):
            if field in clause:
                value = clause[field]
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValidationError(f"Clause at index {i} has non-numeric '{field}'.")
                if not 1 <= float(value) <= 5:
                    raise ValidationError(f"Clause at index {i} has '{field}' outside 1-5.")

        if "risk_category" in clause and not isinstance(clause["risk_category"], str):
            raise ValidationError(f"Clause at index {i} has non-string 'risk_category'.")

    return True
