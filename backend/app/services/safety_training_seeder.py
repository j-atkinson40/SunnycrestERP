"""Seed the 12 monthly OSHA safety training topics.

Called on startup to ensure platform-level training topics exist.
"""

import logging

from sqlalchemy.orm import Session

from app.models.safety_training_topic import SafetyTrainingTopic

logger = logging.getLogger(__name__)

TRAINING_TOPICS = [
    {
        "month_number": 1,
        "topic_key": "lockout_tagout",
        "title": "Lockout/Tagout (LOTO)",
        "description": "Control of hazardous energy during equipment maintenance and servicing. Covers the procedure for isolating energy sources before performing maintenance on machinery.",
        "osha_standard": "29 CFR 1910.147",
        "osha_standard_label": "Control of Hazardous Energy",
        "suggested_duration_minutes": 30,
        "target_roles": ["all"],
        "key_points": [
            "Purpose of LOTO and who it protects",
            "Types of hazardous energy sources in your facility",
            "Steps of a proper LOTO procedure",
            "Authorized vs. affected employee roles",
            "What to do if you find equipment locked out",
        ],
        "discussion_questions": [
            "Where are the energy isolation points on the batch plant mixer?",
            "What should you do if your lock is damaged or the key is lost?",
            "When can you remove someone else's lockout device?",
        ],
        "pdf_filename_template": "LOTO_Training_January_[Year].pdf",
        "is_high_risk": True,
    },
    {
        "month_number": 2,
        "topic_key": "forklift_safety",
        "title": "Forklift and Powered Industrial Truck Safety",
        "description": "Safe operation of forklifts and powered industrial trucks in a precast manufacturing environment. Covers pre-operation inspection, load handling, and pedestrian safety.",
        "osha_standard": "29 CFR 1910.178",
        "osha_standard_label": "Powered Industrial Trucks",
        "suggested_duration_minutes": 30,
        "target_roles": ["driver", "production_staff"],
        "key_points": [
            "Pre-operation inspection checklist",
            "Load capacity and center of gravity",
            "Safe travel speeds and path awareness",
            "Pedestrian right of way",
            "Refueling and battery charging safety",
        ],
        "discussion_questions": [
            "What is the first thing you do before operating a forklift each shift?",
            "How do you handle a load that exceeds the rated capacity?",
            "What are the pedestrian zones in our facility?",
        ],
        "pdf_filename_template": "Forklift_Safety_Training_February_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 3,
        "topic_key": "hazard_communication",
        "title": "Hazard Communication and SDS (Right to Know)",
        "description": "Understanding chemical hazards in the workplace, how to read Safety Data Sheets, and proper labeling requirements under OSHA's HazCom standard.",
        "osha_standard": "29 CFR 1910.1200",
        "osha_standard_label": "Hazard Communication",
        "suggested_duration_minutes": 25,
        "target_roles": ["all"],
        "key_points": [
            "The GHS labeling system and pictograms",
            "How to read a Safety Data Sheet (SDS)",
            "Where to find SDS in your facility",
            "PPE requirements for chemicals you use",
            "Reporting chemical spills and exposures",
        ],
        "discussion_questions": [
            "Where is the SDS binder/station in your work area?",
            "What does the flame pictogram mean on a chemical label?",
            "Who do you call if there is a chemical spill?",
        ],
        "pdf_filename_template": "HazCom_SDS_Training_March_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 4,
        "topic_key": "ppe",
        "title": "Personal Protective Equipment (PPE)",
        "description": "Proper selection, use, care, and limitations of PPE required in precast manufacturing.",
        "osha_standard": "29 CFR 1910.132-138",
        "osha_standard_label": "Personal Protective Equipment",
        "suggested_duration_minutes": 20,
        "target_roles": ["all"],
        "key_points": [
            "PPE required in each area of your facility",
            "How to properly fit and inspect PPE",
            "PPE limitations — what it protects against and what it doesn't",
            "Replacing damaged or worn PPE",
            "Consequences of not wearing required PPE",
        ],
        "discussion_questions": [
            "What PPE is required in the production yard?",
            "How do you know when a hard hat needs to be replaced?",
            "Where do you get replacement PPE if yours is damaged?",
        ],
        "pdf_filename_template": "PPE_Training_April_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 5,
        "topic_key": "electrical_safety",
        "title": "Electrical Safety and Arc Flash Awareness",
        "description": "Electrical hazards in manufacturing environments, safe work practices around electrical equipment, and awareness of arc flash hazards.",
        "osha_standard": "29 CFR 1910.303-333",
        "osha_standard_label": "Electrical Safety",
        "suggested_duration_minutes": 25,
        "target_roles": ["all"],
        "key_points": [
            "Common electrical hazards in precast facilities",
            "What is arc flash and why it is dangerous",
            "Lockout/Tagout and its relationship to electrical work",
            "Qualified vs. unqualified electrical workers",
            "What to do if you encounter exposed wiring or damaged equipment",
        ],
        "discussion_questions": [
            "Who is authorized to work on electrical equipment in our facility?",
            "What should you do if you see a damaged extension cord?",
            "Why should you never bypass a circuit breaker?",
        ],
        "pdf_filename_template": "Electrical_Safety_Training_May_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 6,
        "topic_key": "hearing_conservation",
        "title": "Hearing Conservation",
        "description": "Noise hazards in precast manufacturing, proper use of hearing protection, and understanding audiometric testing requirements.",
        "osha_standard": "29 CFR 1910.95",
        "osha_standard_label": "Occupational Noise Exposure",
        "suggested_duration_minutes": 20,
        "target_roles": ["all"],
        "key_points": [
            "Noise levels in our facility and where hearing protection is required",
            "Types of hearing protection and proper insertion technique",
            "Noise-induced hearing loss — it is permanent",
            "Signs that your hearing may be affected",
            "Audiometric testing — what it is and why it matters",
        ],
        "discussion_questions": [
            "Which areas of our facility require hearing protection?",
            "How do you know if your earplugs are inserted correctly?",
            "When should you request a hearing test?",
        ],
        "pdf_filename_template": "Hearing_Conservation_Training_June_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 7,
        "topic_key": "heat_illness_prevention",
        "title": "Heat Illness Prevention",
        "description": "Recognizing and preventing heat-related illness for outdoor and indoor hot work environments. Especially relevant during summer production months.",
        "osha_standard": "OSHA General Duty Clause Section 5(a)(1)",
        "osha_standard_label": "Heat Illness Prevention",
        "suggested_duration_minutes": 20,
        "target_roles": ["all"],
        "key_points": [
            "Types of heat illness: heat cramps, heat exhaustion, heat stroke",
            "Warning signs in yourself and coworkers",
            "Water, rest, shade — the three keys to prevention",
            "Acclimatization for new workers and returning from time off",
            "What to do if a coworker shows signs of heat stroke",
        ],
        "discussion_questions": [
            "What are the early warning signs of heat exhaustion?",
            "How much water should you drink per hour in hot conditions?",
            "What do you do if a coworker is confused and not sweating?",
        ],
        "pdf_filename_template": "Heat_Illness_Prevention_Training_July_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 8,
        "topic_key": "crane_rigging",
        "title": "Crane and Rigging Safety",
        "description": "Safe operation of overhead cranes and proper rigging techniques for lifting precast concrete products.",
        "osha_standard": "29 CFR 1910.179",
        "osha_standard_label": "Overhead and Gantry Cranes",
        "suggested_duration_minutes": 35,
        "target_roles": ["production_staff"],
        "key_points": [
            "Pre-use crane inspection requirements",
            "Rated load capacity and what factors reduce it",
            "Proper sling selection and inspection",
            "Standard crane hand signals",
            "Exclusion zones during lifts",
            "What to do if a load shifts or equipment malfunctions",
        ],
        "discussion_questions": [
            "What is the rated capacity of our overhead crane?",
            "How do you signal an emergency stop?",
            "What condition makes a wire rope sling unsafe to use?",
        ],
        "pdf_filename_template": "Crane_Rigging_Safety_Training_August_[Year].pdf",
        "is_high_risk": True,
    },
    {
        "month_number": 9,
        "topic_key": "bloodborne_pathogens",
        "title": "Bloodborne Pathogens and First Aid",
        "description": "Understanding bloodborne pathogen risks, proper first aid response, and use of personal protective equipment when responding to injuries.",
        "osha_standard": "29 CFR 1910.1030",
        "osha_standard_label": "Bloodborne Pathogens",
        "suggested_duration_minutes": 20,
        "target_roles": ["all"],
        "key_points": [
            "What are bloodborne pathogens and how they are transmitted",
            "Standard precautions — treat all blood as potentially infectious",
            "Using gloves and other PPE during first aid",
            "Proper disposal of sharps and contaminated materials",
            "Where are first aid kits located and what is in them",
            "When to call 911 vs. handle in-house",
        ],
        "discussion_questions": [
            "Where are the first aid kits in our facility?",
            "What do you put on before helping an injured coworker?",
            "Who is trained in CPR and first aid at our facility?",
        ],
        "pdf_filename_template": "Bloodborne_Pathogens_FirstAid_Training_September_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 10,
        "topic_key": "fall_protection",
        "title": "Fall Protection and Ladder Safety",
        "description": "Fall hazards in precast manufacturing, proper use of fall protection equipment, and safe ladder practices.",
        "osha_standard": "29 CFR 1926.502",
        "osha_standard_label": "Fall Protection",
        "suggested_duration_minutes": 25,
        "target_roles": ["all"],
        "key_points": [
            "Fall hazards specific to our facility: loading docks, elevated platforms, roof access",
            "When fall protection is required (4-foot general industry threshold)",
            "Types of fall protection: guardrails, personal fall arrest, covers",
            "Ladder selection — step vs. extension, rating, angle",
            "Inspecting ladders before use",
            "Three-point contact and other safe ladder practices",
        ],
        "discussion_questions": [
            "What height triggers fall protection requirements?",
            "How do you set an extension ladder at the correct angle?",
            "What do you do with a ladder that has a cracked side rail?",
        ],
        "pdf_filename_template": "Fall_Protection_Ladder_Safety_Training_October_[Year].pdf",
        "is_high_risk": False,
    },
    {
        "month_number": 11,
        "topic_key": "confined_space",
        "title": "Confined Space Awareness",
        "description": "Recognizing permit-required confined spaces in a precast facility, the hazards they present, and the entry procedures that must be followed.",
        "osha_standard": "29 CFR 1910.146",
        "osha_standard_label": "Permit-Required Confined Spaces",
        "suggested_duration_minutes": 30,
        "target_roles": ["all"],
        "key_points": [
            "What makes a space a confined space vs. a permit-required confined space",
            "Confined spaces in our facility: tanks, pits, forms, enclosed areas",
            "Atmospheric hazards: oxygen deficiency, flammable gases, toxic air",
            "The permit system — what it is and why you must not bypass it",
            "Roles: entrant, attendant, entry supervisor",
            "Rescue without entry — never attempt unauthorized rescue",
        ],
        "discussion_questions": [
            "Can you name a confined space in our facility?",
            "What do you do if you see someone entering a confined space without a permit?",
            "Why is it dangerous to enter a confined space to rescue someone?",
        ],
        "pdf_filename_template": "Confined_Space_Awareness_Training_November_[Year].pdf",
        "is_high_risk": True,
    },
    {
        "month_number": 12,
        "topic_key": "emergency_action_fire",
        "title": "Emergency Action Plans and Fire Safety",
        "description": "Your facility emergency action plan, evacuation procedures, fire extinguisher use, and emergency contact protocols.",
        "osha_standard": "29 CFR 1910.38",
        "osha_standard_label": "Emergency Action Plans",
        "suggested_duration_minutes": 20,
        "target_roles": ["all"],
        "key_points": [
            "Your facility emergency action plan — where to find it",
            "Evacuation routes and assembly points",
            "Fire extinguisher types and the PASS technique",
            "When to fight a fire and when to evacuate",
            "Emergency contacts and how to call for help",
            "Special procedures: chemical spill, severe weather, medical emergency",
        ],
        "discussion_questions": [
            "Where is our emergency assembly point?",
            "What type of fire extinguisher is appropriate for an electrical fire?",
            "Who do you contact first in a medical emergency at our facility?",
        ],
        "pdf_filename_template": "Emergency_Action_Fire_Safety_Training_December_[Year].pdf",
        "is_high_risk": False,
    },
]


def seed_training_topics(db: Session) -> None:
    """Insert the 12 monthly OSHA training topics if not already seeded."""
    existing = db.query(SafetyTrainingTopic).count()
    if existing >= 12:
        return

    existing_keys = {
        t.topic_key
        for t in db.query(SafetyTrainingTopic.topic_key).all()
    }

    for topic_data in TRAINING_TOPICS:
        if topic_data["topic_key"] in existing_keys:
            continue
        topic = SafetyTrainingTopic(**topic_data)
        db.add(topic)
        logger.info("Seeded training topic: %s", topic_data["topic_key"])

    db.commit()
