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

        if "recipients" in clause:
            recipients = clause["recipients"]
            if not isinstance(recipients, list):
                raise ValidationError(f"Clause at index {i} has non-list 'recipients'.")
            if any(not isinstance(recipient, str) or not recipient.strip() for recipient in recipients):
                raise ValidationError(f"Clause at index {i} contains an invalid recipient.")

        if "entity_specificity" in clause:
            if clause["entity_specificity"] not in {"specific", "group", "vague"}:
                raise ValidationError(f"Clause at index {i} has invalid 'entity_specificity'.")

        if "retention" in clause:
            retention = clause["retention"]
            if not isinstance(retention, dict):
                raise ValidationError(f"Clause at index {i} has non-object 'retention'.")

            raw_text = retention.get("raw_text", "")
            duration_days = retention.get("duration_days", None)
            if not isinstance(raw_text, str):
                raise ValidationError(f"Clause at index {i} has invalid retention.raw_text.")
            if duration_days is not None and (
                not isinstance(duration_days, (int, float)) or isinstance(duration_days, bool)
            ):
                raise ValidationError(f"Clause at index {i} has invalid retention.duration_days.")

        if "purposes" in clause:
            purposes = clause["purposes"]
            if not isinstance(purposes, list):
                raise ValidationError(f"Clause at index {i} has non-list 'purposes'.")
            if any(not isinstance(purpose, str) or not purpose.strip() for purpose in purposes):
                raise ValidationError(f"Clause at index {i} contains an invalid purpose.")

        if "confidence" in clause:
            confidence = clause["confidence"]
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                raise ValidationError(f"Clause at index {i} has non-numeric 'confidence'.")
            if not 0 <= float(confidence) <= 1:
                raise ValidationError(f"Clause at index {i} has 'confidence' outside 0-1.")

        if "evidence" in clause:
            if not isinstance(clause["evidence"], str):
                raise ValidationError(f"Clause at index {i} has non-string 'evidence'.")

    return True
