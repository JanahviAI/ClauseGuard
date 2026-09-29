import json
import os
import re
import sqlite3
import unicodedata

from rapidfuzz import fuzz, process


class EntityCanonicalizer:
    """Rule-based + fuzzy entity normalization.

    Exact aliases are preferred. Fuzzy matching is only allowed against the
    explicit alias vocabulary and uses a conservative threshold so unrelated
    policy terms are not collapsed together.
    """

    def __init__(self, fuzzy_threshold=90):
        self.fuzzy_threshold = fuzzy_threshold

        self.mapping = {
            # ============================================================
            # LOCATION
            # ============================================================
            "location": "Location",
            "locations": "Location",
            "location data": "Location",
            "location information": "Location",
            "user location": "Location",
            "general location": "Location",
            "general location data": "Location",
            "precise location": "Location",
            "precise location data": "Location",
            "non precise location": "Location",
            "non precise location data": "Location",
            "geolocation": "Location",
            "geolocation data": "Location",
            "gps": "Location",
            "gps data": "Location",
            "street address": "Postal Address",
            "street address data": "Postal Address",
            "postal address": "Postal Address",
            "postal addresses": "Postal Address",
            "home address": "Postal Address",
            "mailing address": "Postal Address",
            "zip postal code": "Postal Code",
            "zip code": "Postal Code",
            "postal code": "Postal Code",

            # ============================================================
            # NETWORK / DEVICE
            # ============================================================
            "ip": "IP Address",
            "ip address": "IP Address",
            "ip addresses": "IP Address",
            "ip-address": "IP Address",
            "internet protocol address": "IP Address",

            "device id": "Device Identifier",
            "device identifier": "Device Identifier",
            "device identifiers": "Device Identifier",
            "device id number": "Device Identifier",
            "device identification": "Device Identifier",

            "advertising id": "Advertising Identifier",
            "advertising identifier": "Advertising Identifier",
            "advertising identifiers": "Advertising Identifier",
            "ad id": "Advertising Identifier",
            "ad identifier": "Advertising Identifier",

            "imei": "IMEI",
            "imei number": "IMEI",

            "mac address": "MAC Address",
            "mac addresses": "MAC Address",

            "browser type": "Browser Type",
            "browser types": "Browser Type",
            "operating system": "Operating System",
            "operating systems": "Operating System",
            "network connection type": "Network Connection Type",
            "network connection": "Network Connection Type",
            "device sensor data": "Device Sensor Data",
            "sensor data": "Device Sensor Data",

            # ============================================================
            # CONTACT / ACCOUNT / IDENTITY
            # ============================================================
            "email": "Email",
            "emails": "Email",
            "e-mail": "Email",
            "email address": "Email",
            "email addresses": "Email",
            "e-mail address": "Email",
            "e-mail addresses": "Email",
            "email correspondence": "Email",
            "email communications": "Email",

            "phone": "Phone Number",
            "phones": "Phone Number",
            "phone number": "Phone Number",
            "phone numbers": "Phone Number",
            "telephone number": "Phone Number",
            "telephone numbers": "Phone Number",
            "mobile number": "Phone Number",
            "mobile numbers": "Phone Number",
            "mobile phone number": "Phone Number",
            "mobile phone numbers": "Phone Number",
            "contact number": "Phone Number",
            "contact numbers": "Phone Number",

            "username": "Username",
            "usernames": "Username",
            "profile name": "Profile Name",
            "profile names": "Profile Name",
            "profile information": "Profile Information",
            "profile data": "Profile Information",
            "profile photo": "Profile Photo",
            "profile picture": "Profile Photo",
            "profile photos": "Profile Photo",
            "profile pictures": "Profile Photo",

            "name": "Name",
            "names": "Name",
            "full name": "Name",
            "full names": "Name",

            "date of birth": "Date of Birth",
            "dates of birth": "Date of Birth",
            "dob": "Date of Birth",

            "age": "Age",
            "ages": "Age",

            "government id": "Government ID",
            "government ids": "Government ID",
            "government-issued id": "Government ID",
            "government-issued ids": "Government ID",
            "identity document": "Government ID",
            "identity documents": "Government ID",

            "passport number": "Passport Number",
            "passport numbers": "Passport Number",

            # ============================================================
            # ACTIVITY / BEHAVIOUR
            # ============================================================
            "browsing history": "Browsing History",
            "browser history": "Browsing History",
            "web browsing history": "Browsing History",
            "browsing histories": "Browsing History",

            "web activity": "Web Activity",
            "web activities": "Web Activity",

            "search history": "Search History",
            "search histories": "Search History",
            "search query": "Search Queries",
            "search queries": "Search Queries",

            "purchase history": "Purchase History",
            "purchase histories": "Purchase History",

            "transaction history": "Transaction History",
            "transaction histories": "Transaction History",

            "listening activity": "Listening Activity",
            "listening activities": "Listening Activity",

            "listening habit": "Listening Habits",
            "listening habits": "Listening Habits",

            "listening history": "Listening History",
            "listening histories": "Listening History",

            "streaming history": "Streaming History",
            "streaming histories": "Streaming History",

            "usage data": "Usage Data",
            "usage information": "Usage Data",
            "usage information data": "Usage Data",

            # ============================================================
            # TRACKING / STORAGE
            # ============================================================
            "cookie": "Cookies",
            "cookies": "Cookies",
            "cookie data": "Cookies",
            "tracking cookie": "Cookies",
            "tracking cookies": "Cookies",

            "browser fingerprint": "Browser Fingerprint",
            "browser fingerprints": "Browser Fingerprint",
            "fingerprint": "Browser Fingerprint",
            "fingerprints": "Browser Fingerprint",

            # ============================================================
            # FINANCIAL / PURCHASE
            # ============================================================
            "credit card": "Payment Information",
            "credit card number": "Payment Information",
            "credit card numbers": "Payment Information",
            "debit card": "Payment Information",
            "debit card number": "Payment Information",

            "payment information": "Payment Information",
            "payment data": "Payment Information",
            "payment details": "Payment Information",

            "payment card details": "Payment Information",
            "payment card detail": "Payment Information",
            "payment cards": "Payment Information",

            "payment currency": "Payment Information",
            "payment currencies": "Payment Information",

            "payment purchase data": "Payment Information",
            "payment and purchase data": "Payment Information",
            "purchase data": "Payment Information",

            "bank account": "Bank Account Information",
            "bank account number": "Bank Account Information",
            "bank account information": "Bank Account Information",

            # ============================================================
            # PERSONAL / SENSITIVE DATA
            # ============================================================
            "personal data": "Personal Data",
            "personal information": "Personal Data",
            "personal information data": "Personal Data",

            "biometric data": "Biometric Data",
            "biometric information": "Biometric Data",

            "voice data": "Voice Data",
            "voice information": "Voice Data",
            "voice recordings": "Voice Data",

            "photos": "Photos",
            "photo": "Photos",
            "images": "Photos",
            "image": "Photos",

            "videos": "Videos",
            "video": "Videos",

            "chat conversations": "Chat Conversations",
            "chat conversation": "Chat Conversations",
            "message data": "Message Data",
            "messaging data": "Message Data",
            "communications": "Communications",
            "communication": "Communications",

            "transcripts": "Transcripts",
            "transcript": "Transcripts",

            "hashed contact information": "Hashed Contact Information",
            "hashed contact data": "Hashed Contact Information",

            "inferences": "Inferences",
            "inference": "Inferences",

            "pseudonymised data": "Pseudonymised Data",
            "pseudonymized data": "Pseudonymised Data",
            "pseudonymised information": "Pseudonymised Data",
            "pseudonymized information": "Pseudonymised Data",

            "registration information": "Registration Information",
            "registration data": "Registration Information",

            "language setting": "Language Setting",
            "language settings": "Language Setting",

            "customer service data": "Customer Service Data",
            "customer service information": "Customer Service Data",

            "survey and research data": "Survey And Research Data",
            "survey data": "Survey And Research Data",
            "research data": "Survey And Research Data",

            # ============================================================
            # THIRD PARTIES / RECIPIENTS
            # ============================================================
            "third party": "Third Parties",
            "third parties": "Third Parties",
            "third party provider": "Third Parties",
            "third party providers": "Third Parties",
            "third party service": "Third Parties",
            "third party services": "Third Parties",
            "third party application": "Third Parties",
            "third party applications": "Third Parties",
            "third party app": "Third Parties",
            "third party apps": "Third Parties",
            "third party platform": "Third Parties",
            "third party platforms": "Third Parties",
            "third party source": "Third Parties",
            "third party sources": "Third Parties",
            "third party device": "Third Parties",
            "third party devices": "Third Parties",
            "third-party websites": "Third Parties",
            "third party websites": "Third Parties",

            "service provider": "Service Providers",
            "service providers": "Service Providers",
            "hosting platform": "Service Providers",
            "hosting platforms": "Service Providers",
            "technical service partner": "Service Providers",
            "technical service partners": "Service Providers",

            "advertising partner": "Advertising Partners",
            "advertising partners": "Advertising Partners",
            "advertising network": "Advertising Networks",
            "advertising networks": "Advertising Networks",
            "advertising or marketing partner": "Advertising Partners",
            "advertising or marketing partners": "Advertising Partners",
            "marketing partner": "Advertising Partners",
            "marketing partners": "Advertising Partners",

            "measurement company": "Measurement Companies",
            "measurement companies": "Measurement Companies",

            "payment partner": "Payment Partners",
            "payment partners": "Payment Partners",

            "merchant": "Merchants",
            "merchants": "Merchants",
            "merchant partner": "Merchant Partners",
            "merchant partners": "Merchant Partners",

            "podcast company": "Podcast Companies",
            "podcast companies": "Podcast Companies",

            "messaging platform": "Messaging Platforms",
            "messaging platforms": "Messaging Platforms",

            "social media": "Social Media",
            "social media application": "Social Media",
            "social media applications": "Social Media",
            "social media platform": "Social Media",
            "social media platforms": "Social Media",

            "voice assistant": "Voice Assistants",
            "voice assistants": "Voice Assistants",

            # ============================================================
            # SOCIAL / CONTACT GRAPH
            # ============================================================
            "contacts": "Contacts",
            "contact": "Contacts",
            "contact list": "Contacts",
            "contact lists": "Contacts",
            "social graph": "Social Graph",

            # ============================================================
            # COMPANY / SERVICE NAMES
            # ============================================================
            "google": "Google",
            "google llc": "Google",
            "google inc": "Google",
            "google ireland limited": "Google",
            "google ireland ltd": "Google",

            "meta": "Meta",
            "meta platforms inc": "Meta",
            "meta platforms inc.": "Meta",
            "meta platforms, inc": "Meta",
            "meta platforms, inc.": "Meta",
            "facebook": "Meta",
            "facebook inc": "Meta",
            "facebook, inc.": "Meta",

            "whatsapp": "WhatsApp",
            "whatsapp llc": "WhatsApp",

            "spotify": "Spotify",
            "spotify ab": "Spotify",
            "spotify technology s.a.": "Spotify",
            "spotify group companies": "Spotify",

            "microsoft": "Microsoft",
            "microsoft corporation": "Microsoft",
            "microsoft corp": "Microsoft",

            "apple": "Apple",
            "apple inc": "Apple",
            "apple inc.": "Apple",

            "amazon": "Amazon",
            "amazon.com inc": "Amazon",
            "amazon.com, inc.": "Amazon",

            "megaphone": "Megaphone",

            # ============================================================
            # OTHER PRIVACY-RELEVANT CONCEPTS
            # ============================================================
            "tailored advertising": "Tailored Advertising",
            "targeted advertising": "Tailored Advertising",
            "personalized advertising": "Tailored Advertising",
            "personalised advertising": "Tailored Advertising",

            "advertising": "Advertising",
        }

        self._aliases = list(self.mapping.keys())

    @staticmethod
    def _normalize(raw_entity):
        value = unicodedata.normalize("NFKC", str(raw_entity))
        value = value.strip().lower()

        value = re.sub(r"[“”\"'`]", "", value)
        value = re.sub(r"[\u2013\u2014]", "-", value)
        value = re.sub(r"[^\w\s,.-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()

        return value

    @staticmethod
    def _remove_plural(value):
        """Return a conservative singular form for simple English plurals."""
        if value.endswith("ies") and len(value) > 4:
            return value[:-3] + "y"

        if value.endswith("ses") and len(value) > 4:
            return value[:-2]

        if value.endswith("s") and not value.endswith("ss") and len(value) > 3:
            return value[:-1]

        return value

    def canonicalize(self, raw_entity):
        if raw_entity is None:
            return ""

        normalized = self._normalize(raw_entity)

        if not normalized:
            return ""

        # ------------------------------------------------------------
        # Exact match
        # ------------------------------------------------------------
        if normalized in self.mapping:
            return self.mapping[normalized]

        # ------------------------------------------------------------
        # Remove trailing punctuation and try again
        # ------------------------------------------------------------
        stripped = re.sub(r"[,.]+$", "", normalized)

        if stripped in self.mapping:
            return self.mapping[stripped]

        # ------------------------------------------------------------
        # Conservative plural normalization
        # ------------------------------------------------------------
        singular = self._remove_plural(stripped)

        if singular in self.mapping:
            return self.mapping[singular]

        # ------------------------------------------------------------
        # Fuzzy match only against explicit aliases
        # ------------------------------------------------------------
        match = process.extractOne(
            normalized,
            self._aliases,
            scorer=fuzz.token_sort_ratio,
        )

        if match and match[1] >= self.fuzzy_threshold:
            return self.mapping[match[0]]

        # Try singular form for fuzzy matching as well.
        if singular != normalized:
            match = process.extractOne(
                singular,
                self._aliases,
                scorer=fuzz.token_sort_ratio,
            )

            if match and match[1] >= self.fuzzy_threshold:
                return self.mapping[match[0]]

        # ------------------------------------------------------------
        # Preserve unknown entities instead of forcing a bad match
        # ------------------------------------------------------------
        return " ".join(
            word.capitalize()
            for word in normalized.split()
        )

    def canonicalize_many(self, entities):
        seen = set()
        result = []

        for entity in entities or []:
            canonical = self.canonicalize(entity)

            if canonical and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)

        return result


class DatabaseLoader:
    def __init__(self, db_path):
        self.db_path = db_path

    def load_extraction(self, extraction_data, canonicalizer):
        service_name = extraction_data.get("service_name")
        category = extraction_data.get("category")
        clauses = extraction_data.get("clauses", [])

        if not service_name:
            raise ValueError("Missing service_name in extraction data")

        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT OR IGNORE INTO services (name, category) VALUES (?, ?)",
                (service_name, category),
            )

            cursor.execute(
                "SELECT id FROM services WHERE name = ?",
                (service_name,),
            )

            service_row = cursor.fetchone()

            if not service_row:
                raise RuntimeError("Failed to retrieve service_id")

            service_id = service_row[0]

            for clause in clauses:
                text = clause.get("text")

                if not text:
                    continue

                severity = clause.get("severity_score")
                specificity = clause.get("specificity_score")
                risk_category = clause.get("risk_category")
                recipients_json = json.dumps(
                    clause.get("recipients", []),
                    ensure_ascii=False,
                )
                entity_specificity = clause.get("entity_specificity")
                retention = clause.get("retention", {}) or {}
                retention_raw = retention.get("raw_text", "")
                retention_days = retention.get("duration_days")
                purposes_json = json.dumps(
                    clause.get("purposes", []),
                    ensure_ascii=False,
                )
                confidence = clause.get("confidence")
                evidence = clause.get("evidence", "")

                cursor.execute(
                    "SELECT id FROM clauses WHERE service_id = ? AND text = ?",
                    (service_id, text),
                )

                clause_row = cursor.fetchone()

                if clause_row:
                    clause_id = clause_row[0]

                    cursor.execute(
                        """UPDATE clauses
                           SET severity_score=?,
                               specificity_score=?,
                               risk_category=?,
                               recipients_json=?,
                               entity_specificity=?,
                               retention_raw=?,
                               retention_days=?,
                               purposes_json=?,
                               confidence=?,
                               evidence=?
                           WHERE id=?""",
                        (
                            severity,
                            specificity,
                            risk_category,
                            recipients_json,
                            entity_specificity,
                            retention_raw,
                            retention_days,
                            purposes_json,
                            confidence,
                            evidence,
                            clause_id,
                        ),
                    )

                else:
                    cursor.execute(
                        """INSERT INTO clauses
                           (service_id, text, severity_score,
                            specificity_score, risk_category,
                            recipients_json, entity_specificity,
                            retention_raw, retention_days,
                            purposes_json, confidence, evidence)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            service_id,
                            text,
                            severity,
                            specificity,
                            risk_category,
                            recipients_json,
                            entity_specificity,
                            retention_raw,
                            retention_days,
                            purposes_json,
                            confidence,
                            evidence,
                        ),
                    )

                    clause_id = cursor.lastrowid

                canonical_entities = canonicalizer.canonicalize_many(
                    clause.get("entities", [])
                )

                for canon_name in canonical_entities:
                    cursor.execute(
                        "INSERT OR IGNORE INTO canonical_entities (name) VALUES (?)",
                        (canon_name,),
                    )

                    cursor.execute(
                        "SELECT id FROM canonical_entities WHERE name = ?",
                        (canon_name,),
                    )

                    entity_id = cursor.fetchone()[0]

                    cursor.execute(
                        """INSERT OR IGNORE INTO clause_entity_mapping
                           (clause_id, entity_id)
                           VALUES (?, ?)""",
                        (clause_id, entity_id),
                    )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()


def process_canonicalization(input_json_path, db_path):
    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    loader = DatabaseLoader(db_path)
    loader.load_extraction(
        data,
        EntityCanonicalizer(),
    )

    print(
        f"Canonicalization and DB loading complete for {input_json_path}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Canonicalize entities and load to SQLite."
    )

    parser.add_argument("input_json")

    args = parser.parse_args()

    root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )

    process_canonicalization(
        args.input_json,
        os.path.join(
            root,
            "data",
            "db",
            "portfolio.db",
        ),
    )