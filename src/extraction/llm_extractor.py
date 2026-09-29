import json
import os
import re
import urllib.error
import urllib.request

try:
    from ..config import get_model, get_provider, get_max_clauses
except ImportError:
    from config import get_model, get_provider, get_max_clauses


SYSTEM_PROMPT = """
You are a privacy-policy clause extraction system.

Analyze each clause using its actual semantic meaning.

Return ONLY valid JSON in this exact structure:

{
  "clauses": [
    {
      "text": "original clause text",
      "entities": [
        {
          "name": "entity name",
          "privacy_relevant": true
        }
      ],
      "severity_score": 1,
      "specificity_score": 1,
      "risk_category": "Data Collection"
    }
  ]
}

ENTITY EXTRACTION RULES:

1. Extract only entities that are genuinely relevant to the privacy
   exposure described in the clause.

2. An entity is privacy_relevant=true ONLY when it represents one of
   these categories:

   A. PERSONAL OR USER DATA
      Examples:
      - Email Address
      - IP Address
      - Phone Number
      - Location
      - Date of Birth
      - Payment Information
      - Browsing History
      - Listening History
      - Device Identifier
      - Voice Data
      - Biometric Data

   B. DATA COLLECTION / TRACKING MECHANISMS
      Examples:
      - Cookies
      - Advertising Identifier
      - Tracking Technologies
      - Device Sensor Data
      - Location Tracking

   C. PRIVACY-RELEVANT RECIPIENTS OR ORGANIZATIONS
      Only when the organization is explicitly involved in collecting,
      processing, sharing, receiving, or controlling personal data.
      Examples:
      - Google
      - Meta
      - Advertising Partners
      - Payment Providers
      - Service Providers

   D. PRIVACY-RELEVANT DATA SOURCES OR SERVICES
      Only when they are directly connected to the collection or
      processing of personal data.
      Examples:
      - Social Media Platforms
      - Payment Services
      - Analytics Providers
      - Advertising Networks

3. Use semantic meaning, NOT simple keyword matching.

4. Do NOT treat every noun, object, product, feature, activity,
   location, legal term, or service mentioned in a clause as an entity.

5. Do NOT extract ordinary objects or products.

   Examples that should normally be privacy_relevant=false:
   - Cars
   - Blenders
   - Food Processors
   - Televisions
   - Tablets
   - Speakers
   - Concerts
   - Playlists
   - Songs
   - Podcasts
   - Artists

6. Do NOT extract ordinary actions or concepts unless they directly
   represent privacy exposure.

   Examples that should normally be false:
   - Processing
   - Business
   - Services
   - Content
   - Controls
   - Users
   - Titles
   - Descriptions
   - Installation
   - Purchase

7. Legal or regulatory references are NOT automatically privacy entities.

   Examples that should normally be false:
   - GDPR
   - Article 15 of the GDPR
   - Swedish Law
   - EU Law
   - Courts
   - Authorities
   - Legal Obligations
   - Adequacy Decisions

   Extract them only when the clause explicitly connects them to a
   concrete privacy exposure or data-processing concept.

8. Privacy rights themselves should NOT normally be extracted as entities.

   Examples that should normally be false:
   - Erasure
   - Data Portability
   - Restriction
   - Right to Object
   - Consent
   - Privacy Controls
   - User Rights

   These should instead be represented through the clause's
   risk_category when appropriate.

9. Generic words such as:
   - data
   - information
   - users
   - service
   - website
   - page
   - account
   - content
   - policy
   - company
   - provider
   - partner

   should NOT normally be entities.

   Only extract them when the surrounding meaning clearly identifies
   a specific privacy concept.

10. The service's own name should NOT be an entity merely because it
    appears in the clause.

11. Do NOT create entities from surrounding clauses.

12. Do NOT infer entities from general knowledge.

13. Preserve meaningful entity names.

    For example:
    "your IP address" -> "IP Address"
    "your precise location" -> "Precise Location"
    "payment card details" -> "Payment Card Details"

14. Avoid overly long entity names that simply copy an entire phrase
    from the clause.

15. If a clause contains no genuine privacy-relevant entity, return:

    "entities": []

EXAMPLES:

Clause:
"We collect your IP address."

Entities:
[
  {
    "name": "IP Address",
    "privacy_relevant": true
  }
]

Clause:
"We collect information about the device you use, including its
operating system and network connection type."

Entities:
[
  {
    "name": "Operating System",
    "privacy_relevant": true
  },
  {
    "name": "Network Connection Type",
    "privacy_relevant": true
  }
]

Clause:
"You can access the service through various automotive platforms."

Entities:
[
  {
    "name": "Automotive Platforms",
    "privacy_relevant": false
  }
]

Clause:
"We may share your personal data with Google."

Entities:
[
  {
    "name": "Personal Data",
    "privacy_relevant": true
  },
  {
    "name": "Google",
    "privacy_relevant": true
  }
]

Clause:
"We offer playlists and podcasts through the Spotify service."

Entities:
[]

Clause:
"You may request erasure of your personal data."

Entities:
[
  {
    "name": "Personal Data",
    "privacy_relevant": true
  }
]

Clause:
"We retain your payment information for as long as required."

Entities:
[
  {
    "name": "Payment Information",
    "privacy_relevant": true
  }
]

Clause:
"We may share personal data with advertising partners."

Entities:
[
  {
    "name": "Personal Data",
    "privacy_relevant": true
  },
  {
    "name": "Advertising Partners",
    "privacy_relevant": true
  }
]

SCORING RULES:

severity_score must be an integer from 1 to 5:
1 = informational/minimal privacy impact
2 = low privacy impact
3 = moderate privacy impact
4 = significant privacy impact
5 = very high privacy impact

specificity_score must be an integer from 1 to 5:
1 = vague/general
2 = somewhat specific
3 = moderately specific
4 = clearly specific
5 = highly specific, concrete or explicitly named

risk_category should describe the primary privacy risk or topic
supported by the clause.

Do not invent facts.
Do not invent entities.
Use only the semantic meaning of the actual clause.
"""


class LLMExtractor:
    """Provider-neutral structured extractor.

    Default behavior is deterministic mock mode so the project works offline.
    Real providers are selected through CLAUSEGUARD_LLM_PROVIDER.
    """

    def __init__(self, service_name, category=None):
        self.service_name = service_name
        self.category = category or "Unknown"
        self.provider = get_provider()
        self.model = get_model(self.provider)

    def extract(self, candidate_clauses):
        if not candidate_clauses:
            return self._build_empty_response()

        results = []
        max_clauses = get_max_clauses()

        for start in range(0, len(candidate_clauses), max_clauses):
            batch = candidate_clauses[start:start + max_clauses]

            if self.provider == "mock":
                parsed = self._call_mock_llm(batch)
            elif self.provider == "ollama":
                parsed = self._call_ollama(batch)
            elif self.provider == "openai":
                parsed = self._call_openai(batch)
            elif self.provider == "anthropic":
                parsed = self._call_anthropic(batch)
            elif self.provider == "gemini":
                parsed = self._call_gemini(batch)
            else:
                raise RuntimeError(
                    f"Unsupported provider: {self.provider}"
                )

            normalized = [
                self._finalize_clause(clause)
                for clause in parsed.get("clauses", [])
            ]
            results.extend(normalized)

        return {
            "service_name": self.service_name,
            "category": self.category,
            "clauses": results,
            "provider": self.provider,
            "model": self.model,
        }

    def _build_empty_response(self):
        return {
            "service_name": self.service_name,
            "category": self.category,
            "clauses": [],
            "provider": self.provider,
            "model": self.model,
        }

    def _call_mock_llm(self, candidate_clauses):
        extracted = []

        for i, text in enumerate(candidate_clauses):
            lower = text.lower()
            entities = []

            keyword_map = [
                (
                    ("location", "gps", "geolocation"),
                    "Location Data"
                ),
                (
                    ("cookie", "cookies"),
                    "Cookies"
                ),
                (
                    ("ip address", "ip-address"),
                    "IP Address"
                ),
                (
                    ("email", "e-mail"),
                    "Email Address"
                ),
                (
                    ("phone number", "telephone", "mobile number"),
                    "Phone Number"
                ),
                (
                    (
                        "device id",
                        "device identifier",
                        "advertising id",
                        "imei",
                        "mac address"
                    ),
                    "Device Identifier"
                ),
                (
                    (
                        "browsing history",
                        "browser history",
                        "web activity"
                    ),
                    "Browsing History"
                ),
            ]

            for keywords, entity in keyword_map:
                if any(k in lower for k in keywords):
                    entities.append(entity)

            if not entities:
                entities.append("General Personal Data")

            recipients = []
            if any(
                keyword in lower
                for keyword in (
                    "share",
                    "third party",
                    "partner",
                    "provider",
                    "affiliate",
                )
            ):
                recipients = [
                    entity
                    for entity in entities
                    if any(
                        marker in entity.lower()
                        for marker in (
                            "partner",
                            "provider",
                            "third",
                            "google",
                            "meta",
                            "amazon",
                            "apple",
                            "microsoft",
                        )
                    )
                ]

            extracted.append({
                "text": text,
                "entities": entities,
                "severity_score": float(3 + (i % 3)),
                "specificity_score": float(2 + (i % 2)),
                "risk_category": "Mock Category",
                "recipients": recipients,
                "entity_specificity": self._infer_entity_specificity(text, entities),
                "retention": self._infer_retention(text),
                "purposes": self._infer_purposes(text),
                "confidence": 0.78,
                "evidence": text[:220],
            })

        return {"clauses": extracted}

    def _call_gemini(self, candidate_clauses):
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set in the environment."
            )

        client = genai.Client(api_key=api_key)

        prompt = (
            SYSTEM_PROMPT
            + "\n\nAnalyze these clauses:\n"
            + json.dumps(
                {"clauses": candidate_clauses},
                ensure_ascii=False
            )
        )

        schema = {
            "type": "OBJECT",
            "properties": {
                "clauses": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "text": {
                                "type": "STRING"
                            },
                            "entities": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "name": {
                                            "type": "STRING"
                                        },
                                        "privacy_relevant": {
                                            "type": "BOOLEAN"
                                        },
                                    },
                                    "required": [
                                        "name",
                                        "privacy_relevant",
                                    ],
                                },
                            },
                            "severity_score": {
                                "type": "INTEGER",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "specificity_score": {
                                "type": "INTEGER",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "risk_category": {
                                "type": "STRING"
                            },
                        },
                        "required": [
                            "text",
                            "entities",
                            "severity_score",
                            "specificity_score",
                            "risk_category",
                        ],
                    },
                }
            },
            "required": ["clauses"],
        }

        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return self._parse_model_json(response.text)

    def _call_openai(self, candidate_clauses):
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"clauses": candidate_clauses},
                        ensure_ascii=False
                    )
                },
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_object"
            },
        }

        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set in the environment."
            )

        body = self._http_json(
            "https://api.openai.com/v1/chat/completions",
            payload,
            {
                "Authorization": "Bearer " + api_key
            },
        )

        content = body["choices"][0]["message"]["content"]

        return self._parse_model_json(content)

    def _call_anthropic(self, candidate_clauses):
        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {"clauses": candidate_clauses},
                        ensure_ascii=False
                    ),
                }
            ],
        }

        body = self._http_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            {
                "x-api-key":
                    os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version":
                    "2023-06-01",
            },
        )

        content_parts = body.get("content", [])

        content = "".join(
            part.get("text", "")
            for part in content_parts
            if part.get("type") == "text"
        )

        return self._parse_model_json(content)

    def _call_ollama(self, candidate_clauses):
        base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434"
        ).rstrip("/")

        schema = {
            "type": "object",
            "properties": {
                "clauses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string"
                            },
                            "entities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string"
                                        },
                                        "privacy_relevant": {
                                            "type": "boolean"
                                        }
                                    },
                                    "required": [
                                        "name",
                                        "privacy_relevant"
                                    ]
                                }
                            },
                            "severity_score": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5
                            },
                            "specificity_score": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5
                            },
                            "risk_category": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "text",
                            "entities",
                            "severity_score",
                            "specificity_score",
                            "risk_category"
                        ]
                    }
                }
            },
            "required": ["clauses"]
        }

        payload = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {
                "temperature": 0
            },
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"clauses": candidate_clauses},
                        ensure_ascii=False
                    )
                }
            ],
        }

        body = self._http_json(
            f"{base_url}/api/chat",
            payload,
            {},
            timeout=600,
        )

        content = body.get(
            "message",
            {}
        ).get(
            "content",
            ""
        )

        if not content.strip():
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        return self._parse_model_json(content)

    def _http_json(
        self,
        url,
        payload,
        extra_headers,
        timeout=120
    ):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **extra_headers
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(
                "utf-8",
                errors="replace"
            )

            raise RuntimeError(
                f"LLM HTTP {exc.code} from {url}: {detail}"
            ) from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach LLM provider at {url}: "
                f"{exc.reason}"
            ) from exc

    @staticmethod
    def _clean_entities(entities):
        """Keep entities that are relevant to privacy/data-risk analysis."""

        blocked = {
            "we", "you", "they", "them", "their", "us", "our", "your",
            "data", "information", "people", "person", "persons",
            "users", "user", "policy", "privacy policy",
            "service", "services", "website", "websites",
            "links", "link", "content", "account", "accounts",
            "page", "pages", "settings", "setting",
            "social", "explicit content", "private session",

            "app", "applications", "application", "library",
            "playlist", "playlists", "cooking", "cooking podcast",
            "food processor", "ai dj", "ai playlist",
            "spotify kids", "summer rewind", "time capsule",
            "platform rules", "user guidelines",
            "spotify service option",
            "spotify application version",
            "spotify for creators community guidelines",

            "4g", "5g", "lte", "wi-fi", "wifi", "bluetooth",
            "aes", "transport layer security (tls)",
            "operating system", "mobile", "device", "devices",
            "speaker devices", "televisions",

            "sweden", "country", "country / region",
            "section 5", "eu law",
        }

        privacy_terms = {
            "data", "personal data", "user data", "usage data",
            "technical data", "profile information", "account data",
            "spotify account data", "registration information",
            "contact information", "email", "email address",
            "phone number", "mobile phone number",
            "street address", "street address data", "zip/postal code",
            "date of birth", "age", "age check data",
            "identity document", "photo of identity document",
            "photo of face", "other directly identifying information",
            "ip address", "ip addresses", "device id", "device ids",
            "device identifier", "device sensor data",
            "location", "location data", "precise location data",
            "browsing history", "search queries", "streaming history",
            "listening habits", "users' listening",
            "usage data", "message data", "voice data",
            "audio recordings of your voice", "transcripts",
            "payment information", "payment data",
            "payment card details", "payment and purchase data",
            "purchase data", "payment currency", "billing information",
            "tax information", "cookie data",
            "advertising", "advertising space", "tailored advertising",
            "engagement with ads", "ad partners",
            "personalised recommendations", "interests",
            "preferences", "profile", "profile name",
            "profile photo", "profile picture",
            "public playlists", "followers",
            "interactions with other spotify users",
            "pseudonymised data",
            "customer service data", "survey and research data",
            "real-time usage of spotify",
            "network connection type",
            "network and device performance",
            "url information",
            "marketing", "promotions",
            "data controller", "data portability",
            "user rights", "legal basis", "legal obligation",
            "data protection law", "standard contractual clauses",
            "mandatory data retention laws",
            "consent", "contract", "litigation",
            "government orders", "data transfer",
        }

        organization_markers = {
            "google", "meta", "facebook", "whatsapp", "microsoft",
            "apple", "amazon", "spotify", "university", "college",
            "company", "companies", "partner", "partners",
            "ad partners", "third party", "third-party",
        }

        cleaned = []

        for entity in entities:
            if not isinstance(entity, str):
                continue

            entity = re.sub(
                r"\s+",
                " ",
                entity
            ).strip()

            if not entity:
                continue

            normalized = entity.lower()

            if normalized in blocked:
                continue

            if normalized in privacy_terms:
                if entity not in cleaned:
                    cleaned.append(entity)
                continue

            if (
                normalized in organization_markers
                or any(
                    marker in normalized
                    for marker in organization_markers
                )
            ):
                if entity not in cleaned:
                    cleaned.append(entity)
                continue

            if re.fullmatch(
                r"(section|chapter|part|page)\s+[\w\d-]+",
                normalized,
            ):
                continue

            if normalized in {
                "4g", "5g", "lte", "wi-fi", "wifi",
                "bluetooth", "aes", "tls",
            }:
                continue

            if (
                len(entity.split()) == 1
                and normalized in {
                    "app", "applications", "application",
                    "companies", "contract", "provider",
                    "offers", "notices", "gifts", "contests",
                    "sweepstakes", "services", "products",
                    "devices", "mobile", "library",
                    "playlist", "playlists", "profile",
                }
            ):
                continue

            if len(entity.split()) >= 2:
                if entity not in cleaned:
                    cleaned.append(entity)

        return cleaned

    @staticmethod
    def _apply_entity_quality_filter(entities):
        """Remove generic, self-referential, and non-privacy entities.

        This filter is provider-independent. The LLM first performs
        semantic classification, and this deterministic layer removes
        obvious noise before canonicalization and scoring.
        """

        blocked_exact = {
            # Service/policy self-reference
            "spotify",

            # Generic concepts that are too broad to score alone
            "personal data",
            "user data",
            "data",
            "information",
            "privacy",
            "privacy policy",

            # Generic concepts
            "audio",
            "content",
            "services",
            "service",
            "business",
            "processing",
            "users",
            "user",
            "people",
            "company",
            "companies",
            "provider",
            "providers",
            "partner",
            "partners",

            # Generic advertising concepts
            "advertising",
            "marketing",
            "promotions",
            "advertising space",

            # Generic platform/content concepts
            "social media",
            "profile",
            "account",
            "accounts",
            "products",
            "devices",
            "mobile",
            "application",
            "applications",
            "app",
            "library",
            "playlist",
            "playlists",

            # Legal/privacy-right concepts
            "gdpr",
            "data portability",
            "user rights",
            "consent",
            "legal obligation",
            "legal obligations",
            "legal basis",
            "swedish law",
            "eu law",
            "courts",
            "authorities",
        }

        ordinary_content = {
            "song",
            "songs",
            "podcast",
            "podcasts",
            "artist",
            "artists",
            "concert",
            "concerts",
            "playlist",
            "playlists",
            "television",
            "televisions",
            "tablet",
            "tablets",
            "speaker",
            "speakers",
            "car",
            "cars",
            "automotive",
        }

        vague_single_words = {
            "object",
            "processing",
            "installation",
            "purchase",
            "offers",
            "controls",
            "titles",
            "descriptions",
            "categories",
            "days",
            "mobile",
            "library",
        }

        cleaned = []

        for entity in entities:
            if not isinstance(entity, str):
                continue

            entity = re.sub(
                r"\s+",
                " ",
                entity
            ).strip()

            if not entity:
                continue

            normalized = entity.casefold()

            # Remove exact generic/self-referential entities.
            if normalized in blocked_exact:
                continue

            # Remove obvious ordinary products/content.
            if normalized in ordinary_content:
                continue

            # Remove vague single-word nouns.
            if (
                len(entity.split()) == 1
                and normalized in vague_single_words
            ):
                continue

            # Remove Spotify's own service/platform references.
            if (
                normalized.startswith("spotify ")
                or normalized.endswith(" spotify")
            ):
                if any(
                    word in normalized
                    for word in (
                        "service",
                        "application",
                        "account",
                        "platform",
                        "terms",
                        "policy",
                    )
                ):
                    continue

            if entity not in cleaned:
                cleaned.append(entity)

        return cleaned

    @staticmethod
    def _infer_recipients_from_entities(entities):
        recipient_markers = (
            "partner",
            "provider",
            "network",
            "company",
            "google",
            "meta",
            "amazon",
            "apple",
            "microsoft",
            "third parties",
            "service providers",
        )
        recipients = []
        for entity in entities:
            if not isinstance(entity, str):
                continue
            lower = entity.lower()
            if any(marker in lower for marker in recipient_markers):
                recipients.append(entity)

        deduped = []
        for recipient in recipients:
            if recipient not in deduped:
                deduped.append(recipient)
        return deduped

    @staticmethod
    def _infer_entity_specificity(text, entities):
        if entities and any(
            len(entity.split()) >= 2
            for entity in entities
            if isinstance(entity, str)
        ):
            return "specific"

        lower = text.lower()
        if any(token in lower for token in ("third party", "partners", "affiliates", "providers")):
            return "group"

        return "vague"

    @staticmethod
    def _infer_retention(text):
        lower = text.lower()
        match = re.search(
            r"(\d+)\s*(day|days|month|months|year|years)",
            lower,
        )
        duration_days = None
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("day"):
                duration_days = value
            elif unit.startswith("month"):
                duration_days = value * 30
            elif unit.startswith("year"):
                duration_days = value * 365

        if "as long as necessary" in lower or "as long as required" in lower:
            raw = "as long as necessary"
        elif "until" in lower and "delete" in lower:
            raw = "until account deletion"
        elif match:
            raw = match.group(0)
        else:
            raw = ""

        return {
            "raw_text": raw,
            "duration_days": duration_days,
        }

    @staticmethod
    def _infer_purposes(text):
        lower = text.lower()
        mapping = {
            "advertis": "Advertising",
            "market": "Marketing",
            "security": "Security",
            "fraud": "Fraud Prevention",
            "analytics": "Analytics",
            "improve": "Service Improvement",
            "support": "Customer Support",
            "legal": "Legal Compliance",
            "payment": "Payments",
            "personaliz": "Personalization",
        }
        purposes = []
        for needle, label in mapping.items():
            if needle in lower and label not in purposes:
                purposes.append(label)
        return purposes

    @staticmethod
    def _finalize_clause(clause):
        text = clause.get("text", "")
        entities = clause.get("entities", [])
        if not isinstance(entities, list):
            entities = []
            clause["entities"] = entities

        recipients = clause.get("recipients")
        if not isinstance(recipients, list):
            recipients = LLMExtractor._infer_recipients_from_entities(entities)

        entity_specificity = clause.get("entity_specificity")
        if entity_specificity not in {"specific", "group", "vague"}:
            entity_specificity = LLMExtractor._infer_entity_specificity(text, entities)

        retention = clause.get("retention")
        if not isinstance(retention, dict):
            retention = LLMExtractor._infer_retention(text)
        retention.setdefault("raw_text", "")
        retention.setdefault("duration_days", None)

        purposes = clause.get("purposes")
        if not isinstance(purposes, list):
            purposes = LLMExtractor._infer_purposes(text)
        else:
            purposes = [
                purpose.strip()
                for purpose in purposes
                if isinstance(purpose, str) and purpose.strip()
            ]

        confidence = clause.get("confidence", 0.75)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.75
        confidence = max(0.0, min(1.0, confidence))

        evidence = clause.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            evidence = text[:220]

        clause["recipients"] = recipients
        clause["entity_specificity"] = entity_specificity
        clause["retention"] = retention
        clause["purposes"] = purposes
        clause["confidence"] = confidence
        clause["evidence"] = evidence
        return clause

    @staticmethod
    def _parse_model_json(content):
        content = content.strip()

        if not content:
            raise RuntimeError(
                "LLM returned an empty response."
            )

        # Remove markdown code fences if present.
        if content.startswith("```"):
            content = re.sub(
                r"^```(?:json)?\s*",
                "",
                content,
                flags=re.I
            )

            content = re.sub(
                r"\s*```$",
                "",
                content
            )

        try:
            parsed = json.loads(content)

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"LLM returned invalid JSON: {content[:500]}"
            ) from exc

        if not isinstance(parsed, dict):
            raise RuntimeError(
                "LLM JSON must be a JSON object."
            )

        clauses = parsed.get("clauses")

        if not isinstance(clauses, list):
            raise RuntimeError(
                "LLM JSON must contain a top-level 'clauses' array."
            )

        # Validate model output before it reaches the project's validator.
        for i, clause in enumerate(clauses):

            if not isinstance(clause, dict):
                raise RuntimeError(
                    f"LLM returned an invalid clause at index {i}."
                )

            required = [
                "text",
                "entities",
                "severity_score",
                "specificity_score",
                "risk_category",
            ]

            missing = [
                field
                for field in required
                if field not in clause
            ]

            if missing:
                raise RuntimeError(
                    f"LLM clause at index {i} is missing: "
                    + ", ".join(missing)
                )

            severity = clause["severity_score"]
            specificity = clause["specificity_score"]

            if (
                not isinstance(severity, (int, float))
                or isinstance(severity, bool)
                or not 1 <= severity <= 5
            ):
                raise RuntimeError(
                    f"LLM returned invalid severity_score "
                    f"{severity!r} at clause {i}."
                )

            if (
                not isinstance(specificity, (int, float))
                or isinstance(specificity, bool)
                or not 1 <= specificity <= 5
            ):
                raise RuntimeError(
                    f"LLM returned invalid specificity_score "
                    f"{specificity!r} at clause {i}."
                )

            if not isinstance(clause["entities"], list):
                raise RuntimeError(
                    f"LLM returned invalid entities at clause {i}."
                )

            semantic_entities = []

            for entity in clause["entities"]:
                if isinstance(entity, str):
                    name = entity
                    privacy_relevant = True
                elif isinstance(entity, dict):
                    name = entity.get("name")
                    privacy_relevant = entity.get(
                        "privacy_relevant"
                    )
                else:
                    raise RuntimeError(
                        f"LLM returned invalid entity at clause {i}."
                    )

                if (
                    not isinstance(name, str)
                    or not name.strip()
                ):
                    raise RuntimeError(
                        f"LLM returned invalid entity name "
                        f"at clause {i}."
                    )

                if not isinstance(privacy_relevant, bool):
                    raise RuntimeError(
                        f"LLM returned invalid privacy_relevant "
                        f"value at clause {i}."
                    )

                # Only entities that the LLM identifies as
                # privacy-relevant enter the quality filter.
                if privacy_relevant:
                    clean_name = re.sub(
                        r"\s+",
                        " ",
                        name
                    ).strip()

                    if (
                        clean_name
                        and clean_name not in semantic_entities
                    ):
                        semantic_entities.append(
                            clean_name
                        )

            # Apply deterministic quality filtering after
            # semantic LLM classification.
            clause["entities"] = (
                LLMExtractor._apply_entity_quality_filter(
                    semantic_entities
                )
            )

            if not isinstance(
                clause["risk_category"],
                str
            ):
                raise RuntimeError(
                    f"LLM returned invalid risk_category "
                    f"at clause {i}."
                )

        return parsed