"""Compliance Intelligence Service — state-specific compliance requirements for manufacturers.

NEW: no existing equivalent. Determines required compliance items based on
state, business type, and operational characteristics (CDL drivers, vehicles, forklifts).
"""

import logging

logger = logging.getLogger(__name__)


COMPLIANCE_MATRIX = {
    "NY": {
        "precast_manufacturer": {
            "always_required": [
                {
                    "item_key": "compliance.osha_300_log",
                    "reason": "Required for all NY manufacturers",
                    "frequency": "annual",
                },
                {
                    "item_key": "compliance.npca_certification",
                    "reason": "NPCA certification required for Wilbert licensees",
                    "frequency": "annual",
                },
            ],
            "if_has_cdl_drivers": [
                {
                    "item_key": "compliance.cdl_renewal",
                    "reason": "NY CDL renewals every 8 years",
                    "auto_create_per_driver": True,
                },
                {
                    "item_key": "compliance.drug_testing",
                    "reason": "DOT drug testing required for CDL drivers",
                },
            ],
            "if_has_commercial_vehicles": [
                {
                    "item_key": "compliance.dot_registration",
                    "reason": "NY DOT vehicle registration",
                    "frequency": "annual",
                    "auto_create_per_vehicle": True,
                },
                {
                    "item_key": "compliance.hut_filing",
                    "reason": "NY Highway Use Tax for vehicles over 18,000 lbs",
                    "frequency": "annual",
                },
            ],
            "if_has_forklifts": [
                {
                    "item_key": "compliance.forklift_cert",
                    "reason": "OSHA forklift certification every 3 years",
                    "auto_create_per_operator": True,
                },
                {
                    "item_key": "compliance.forklift_inspection",
                    "reason": "Daily forklift inspection log",
                    "frequency": "daily",
                },
            ],
        },
    },
    "PA": {
        "precast_manufacturer": {
            "always_required": [
                {
                    "item_key": "compliance.osha_300_log",
                    "reason": "Required for all PA manufacturers",
                    "frequency": "annual",
                },
                {
                    "item_key": "compliance.npca_certification",
                    "reason": "NPCA certification required for Wilbert licensees",
                    "frequency": "annual",
                },
            ],
            "if_has_cdl_drivers": [
                {
                    "item_key": "compliance.cdl_renewal",
                    "reason": "PA CDL renewals every 4 years",
                    "auto_create_per_driver": True,
                },
                {
                    "item_key": "compliance.drug_testing",
                    "reason": "DOT drug testing required for CDL drivers",
                },
            ],
            "if_has_commercial_vehicles": [
                {
                    "item_key": "compliance.dot_registration",
                    "reason": "PA DOT vehicle registration",
                    "frequency": "annual",
                    "auto_create_per_vehicle": True,
                },
            ],
            "if_has_forklifts": [
                {
                    "item_key": "compliance.forklift_cert",
                    "reason": "OSHA forklift certification every 3 years",
                    "auto_create_per_operator": True,
                },
                {
                    "item_key": "compliance.forklift_inspection",
                    "reason": "Daily forklift inspection log",
                    "frequency": "daily",
                },
            ],
        },
    },
    "OH": {
        "precast_manufacturer": {
            "always_required": [
                {
                    "item_key": "compliance.osha_300_log",
                    "reason": "Required for all OH manufacturers",
                    "frequency": "annual",
                },
                {
                    "item_key": "compliance.npca_certification",
                    "reason": "NPCA certification required for Wilbert licensees",
                    "frequency": "annual",
                },
            ],
            "if_has_cdl_drivers": [
                {
                    "item_key": "compliance.cdl_renewal",
                    "reason": "OH CDL renewals every 4 years",
                    "auto_create_per_driver": True,
                },
                {
                    "item_key": "compliance.drug_testing",
                    "reason": "DOT drug testing required for CDL drivers",
                },
            ],
            "if_has_commercial_vehicles": [
                {
                    "item_key": "compliance.dot_registration",
                    "reason": "OH DOT vehicle registration",
                    "frequency": "annual",
                    "auto_create_per_vehicle": True,
                },
            ],
            "if_has_forklifts": [
                {
                    "item_key": "compliance.forklift_cert",
                    "reason": "OSHA forklift certification every 3 years",
                    "auto_create_per_operator": True,
                },
                {
                    "item_key": "compliance.forklift_inspection",
                    "reason": "Daily forklift inspection log",
                    "frequency": "daily",
                },
            ],
        },
    },
    "NJ": {
        "precast_manufacturer": {
            "always_required": [
                {
                    "item_key": "compliance.osha_300_log",
                    "reason": "Required for all NJ manufacturers",
                    "frequency": "annual",
                },
                {
                    "item_key": "compliance.npca_certification",
                    "reason": "NPCA certification required for Wilbert licensees",
                    "frequency": "annual",
                },
                {
                    "item_key": "compliance.epa_stormwater",
                    "reason": "NJ NJDEP stormwater permit required for all manufacturers",
                },
            ],
            "if_has_cdl_drivers": [
                {
                    "item_key": "compliance.cdl_renewal",
                    "reason": "NJ CDL renewals every 4 years",
                    "auto_create_per_driver": True,
                },
                {
                    "item_key": "compliance.drug_testing",
                    "reason": "DOT drug testing required for CDL drivers",
                },
            ],
            "if_has_commercial_vehicles": [
                {
                    "item_key": "compliance.dot_registration",
                    "reason": "NJ DOT vehicle registration",
                    "frequency": "annual",
                    "auto_create_per_vehicle": True,
                },
            ],
            "if_has_forklifts": [
                {
                    "item_key": "compliance.forklift_cert",
                    "reason": "OSHA forklift certification every 3 years",
                    "auto_create_per_operator": True,
                },
                {
                    "item_key": "compliance.forklift_inspection",
                    "reason": "Daily forklift inspection log",
                    "frequency": "daily",
                },
            ],
        },
    },
}


class ComplianceIntelligenceService:
    """Determines required compliance items based on state, business type, and operations."""

    @staticmethod
    def get_required_items(
        state: str,
        business_type: str = "precast_manufacturer",
        has_cdl_drivers: bool = False,
        cdl_driver_count: int = 0,
        has_commercial_vehicles: bool = False,
        vehicle_count: int = 0,
        has_forklifts: bool = False,
        forklift_count: int = 0,
        forklift_operator_count: int = 0,
    ) -> list[dict]:
        """Return the full list of required compliance items based on inputs.

        Merges always_required with conditional items based on the operational
        characteristics provided. Each returned item includes the item_key,
        reason, and any auto-creation metadata.
        """
        state_upper = state.upper() if state else ""
        matrix = COMPLIANCE_MATRIX.get(state_upper, {}).get(business_type, {})

        if not matrix:
            # Fall back to a generic set if state not in matrix
            # Use NY as the baseline since most requirements are federal/OSHA
            matrix = COMPLIANCE_MATRIX.get("NY", {}).get(business_type, {})
            if matrix:
                logger.info(
                    "No compliance matrix for state=%s, falling back to NY baseline",
                    state_upper,
                )

        required = []

        # Always required
        for item in matrix.get("always_required", []):
            required.append({
                **item,
                "condition": "always",
                "state": state_upper,
            })

        # CDL drivers
        if has_cdl_drivers or cdl_driver_count > 0:
            for item in matrix.get("if_has_cdl_drivers", []):
                entry = {
                    **item,
                    "condition": "cdl_drivers",
                    "state": state_upper,
                }
                if item.get("auto_create_per_driver"):
                    entry["instance_count"] = max(cdl_driver_count, 1)
                required.append(entry)

        # Commercial vehicles
        if has_commercial_vehicles or vehicle_count > 0:
            for item in matrix.get("if_has_commercial_vehicles", []):
                entry = {
                    **item,
                    "condition": "commercial_vehicles",
                    "state": state_upper,
                }
                if item.get("auto_create_per_vehicle"):
                    entry["instance_count"] = max(vehicle_count, 1)
                required.append(entry)

        # Forklifts
        if has_forklifts or forklift_count > 0:
            for item in matrix.get("if_has_forklifts", []):
                entry = {
                    **item,
                    "condition": "forklifts",
                    "state": state_upper,
                }
                if item.get("auto_create_per_operator"):
                    entry["instance_count"] = max(forklift_operator_count, 1)
                required.append(entry)

        return required

    @staticmethod
    def generate_onboarding_questions(
        state: str, business_type: str = "precast_manufacturer"
    ) -> list[dict]:
        """Generate minimal smart questions that unlock compliance configuration.

        These are the questions to ask during onboarding to determine which
        conditional compliance items apply to this licensee.
        """
        questions = [
            {
                "question_key": "cdl_drivers",
                "question": "Do any of your employees hold a Commercial Driver's License (CDL)?",
                "type": "boolean",
                "follow_up": {
                    "if_yes": {
                        "question_key": "cdl_driver_count",
                        "question": "How many CDL drivers do you employ?",
                        "type": "number",
                    },
                },
                "unlocks": ["compliance.cdl_renewal", "compliance.drug_testing"],
            },
            {
                "question_key": "commercial_vehicles",
                "question": "Do you operate commercial vehicles (delivery trucks, flatbeds, etc.)?",
                "type": "boolean",
                "follow_up": {
                    "if_yes": {
                        "question_key": "vehicle_count",
                        "question": "How many commercial vehicles do you operate?",
                        "type": "number",
                    },
                },
                "unlocks": ["compliance.dot_registration", "compliance.hut_filing"],
            },
            {
                "question_key": "forklifts",
                "question": "Do you operate forklifts or powered industrial trucks at your facility?",
                "type": "boolean",
                "follow_up": {
                    "if_yes": [
                        {
                            "question_key": "forklift_count",
                            "question": "How many forklifts/powered industrial trucks?",
                            "type": "number",
                        },
                        {
                            "question_key": "forklift_operator_count",
                            "question": "How many employees are trained to operate them?",
                            "type": "number",
                        },
                    ],
                },
                "unlocks": ["compliance.forklift_cert", "compliance.forklift_inspection"],
            },
        ]

        # Add state-specific questions
        state_upper = state.upper() if state else ""
        if state_upper == "NJ":
            questions.append({
                "question_key": "stormwater_discharge",
                "question": "Does your facility discharge stormwater? (Most NJ manufacturers do.)",
                "type": "boolean",
                "default": True,
                "unlocks": ["compliance.epa_stormwater"],
            })

        return questions
