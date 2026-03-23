#!/usr/bin/env python3
"""Generate 12 monthly OSHA safety training PDF documents.

Run once at build time. Outputs to backend/static/safety-templates/.
"""

import os

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "backend", "static", "safety-templates")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DARK_GRAY = HexColor("#1a1a2e")
ACCENT = HexColor("#e63946")
LIGHT_GRAY = HexColor("#f8f9fa")
MID_GRAY = HexColor("#6c757d")


def build_pdf(
    filename,
    topic_title,
    osha_standard,
    osha_label,
    why_it_matters,
    key_points,
    in_our_facility,
    discussion_questions,
    **_extra,
):
    filepath = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    company_style = ParagraphStyle(
        "Company", fontSize=11, textColor=MID_GRAY, spaceAfter=4, fontName="Helvetica"
    )
    header_style = ParagraphStyle(
        "Header",
        fontSize=9,
        textColor=MID_GRAY,
        spaceAfter=2,
        fontName="Helvetica-Bold",
        leading=12,
    )
    title_style = ParagraphStyle(
        "Title",
        fontSize=22,
        textColor=DARK_GRAY,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        leading=26,
    )
    osha_style = ParagraphStyle(
        "OSHA", fontSize=9, textColor=MID_GRAY, spaceAfter=16, fontName="Helvetica"
    )
    section_label = ParagraphStyle(
        "SectionLabel",
        fontSize=8,
        textColor=ACCENT,
        spaceAfter=6,
        fontName="Helvetica-Bold",
        leading=10,
        spaceBefore=14,
    )
    body_style = ParagraphStyle(
        "Body",
        fontSize=10,
        textColor=DARK_GRAY,
        spaceAfter=4,
        fontName="Helvetica",
        leading=15,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        fontSize=10,
        textColor=DARK_GRAY,
        spaceAfter=4,
        fontName="Helvetica",
        leading=15,
        leftIndent=16,
        firstLineIndent=-16,
    )
    question_style = ParagraphStyle(
        "Question",
        fontSize=10,
        textColor=DARK_GRAY,
        spaceAfter=8,
        fontName="Helvetica-Oblique",
        leading=14,
        leftIndent=16,
        firstLineIndent=-16,
    )
    footer_style = ParagraphStyle(
        "Footer",
        fontSize=8,
        textColor=MID_GRAY,
        spaceAfter=2,
        fontName="Helvetica",
        alignment=TA_CENTER,
    )

    story = []

    # Company name (personalized or placeholder)
    company_name = _extra.get("_company_name", "[COMPANY NAME]")
    story.append(Paragraph(company_name, company_style))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=12)
    )

    # Header
    story.append(Paragraph("SAFETY TRAINING", header_style))
    story.append(Paragraph(topic_title, title_style))
    story.append(
        Paragraph(f"OSHA Standard: {osha_standard} &mdash; {osha_label}", osha_style)
    )

    # Date / Location
    date_data = [["Date:", "_" * 25, "Location:", "_" * 25]]
    date_table = Table(
        date_data, colWidths=[0.6 * inch, 2.4 * inch, 0.8 * inch, 2.9 * inch]
    )
    date_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, 0), MID_GRAY),
                ("TEXTCOLOR", (2, 0), (2, 0), MID_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(date_table)
    story.append(Spacer(1, 12))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=4)
    )

    # Why it matters
    story.append(Paragraph("WHY THIS MATTERS", section_label))
    story.append(Paragraph(why_it_matters, body_style))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=4)
    )

    # Key points
    story.append(Paragraph("WHAT YOU NEED TO KNOW", section_label))
    for i, point in enumerate(key_points, 1):
        story.append(Paragraph(f"{i}.&nbsp;&nbsp;{point}", bullet_style))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=4)
    )

    # In our facility
    story.append(Paragraph("IN OUR FACILITY", section_label))
    story.append(Paragraph(in_our_facility, body_style))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=4)
    )

    # Discussion questions
    story.append(Paragraph("DISCUSSION QUESTIONS", section_label))
    for i, q in enumerate(discussion_questions, 1):
        story.append(Paragraph(f"{i}.&nbsp;&nbsp;{q}", question_style))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY, spaceAfter=12)
    )

    # Acknowledgment
    story.append(Paragraph("EMPLOYEE ACKNOWLEDGMENT", section_label))
    story.append(
        Paragraph(
            f"I have read and understood the {topic_title} training "
            f"material presented today.",
            body_style,
        )
    )
    story.append(Spacer(1, 8))
    ack_data = [
        ["Name (print):", "_" * 40],
        ["", ""],
        ["Signature:", "_" * 40],
        ["", ""],
        ["Date:", "_" * 20],
    ]
    ack_table = Table(ack_data, colWidths=[1.2 * inch, 5.5 * inch])
    ack_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), MID_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(ack_table)

    story.append(Spacer(1, 16))
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=6)
    )
    story.append(
        Paragraph(
            "Platform Safety Training Program &middot; "
            "This document may be replaced with a company-specific "
            "training program. Contact your safety manager with questions.",
            footer_style,
        )
    )

    doc.build(story)
    print(f"  Generated: {filename}")


# ── All 12 training topics ──────────────────────────────────────────────────

TRAININGS = [
    {
        "filename": "safety_training_01_lockout_tagout.pdf",
        "topic_title": "Lockout/Tagout (LOTO)",
        "osha_standard": "29 CFR 1910.147",
        "osha_label": "Control of Hazardous Energy",
        "why_it_matters": "Unexpected startup of machinery or release of stored energy kills and seriously injures workers every year. LOTO procedures ensure that equipment cannot be energized while someone is working on it. In a precast plant, mixers, conveyors, and compressors all present serious energy hazards.",
        "key_points": [
            "Before servicing any equipment &mdash; shut it down, isolate the energy source, and apply your personal lock",
            "Each worker performing maintenance applies their own lock &mdash; never share locks",
            "Only the person who applied a lock may remove it",
            "Types of hazardous energy: electrical, hydraulic, pneumatic, mechanical, gravitational, thermal",
            "If you find equipment locked out &mdash; do not attempt to remove the lock or bypass it",
            "Affected employees (those who work near but not on equipment) must stay clear of the area",
        ],
        "in_our_facility": "Your facility has energy isolation points on all major equipment &mdash; batch plant mixers, conveyors, compressors, and forming equipment. Lockout devices and locks are located at [LOCATION &mdash; FILL IN]. Any equipment with a lockout tag applied must be treated as energized until the lock is removed by the person who applied it.",
        "discussion_questions": [
            "Where are the energy isolation points on the batch plant mixer?",
            "What do you do if your lock is damaged or you lose the key?",
            "When is it acceptable to remove another worker's lockout device?",
        ],
    },
    {
        "filename": "safety_training_02_forklift_safety.pdf",
        "topic_title": "Forklift and Powered Industrial Truck Safety",
        "osha_standard": "29 CFR 1910.178",
        "osha_label": "Powered Industrial Trucks",
        "why_it_matters": "Forklifts are involved in nearly 85 fatal accidents and 34,900 serious injuries annually in the US. In a precast yard, heavy vault and product loads combined with truck traffic make forklift safety critical for everyone on site.",
        "key_points": [
            "Inspect the forklift before every shift using the daily checklist &mdash; do not operate a defective forklift",
            "Never exceed the rated load capacity shown on the data plate",
            "Travel with forks lowered (6-12 inches off the ground), mast tilted back",
            "Pedestrians always have the right of way &mdash; slow down and sound your horn at intersections",
            "Never carry passengers or allow anyone to stand under raised forks",
            "Report any damage or mechanical issues immediately &mdash; do not leave a problem for the next shift",
        ],
        "in_our_facility": "Our forklifts are used to move product in the yard, load delivery trucks, and handle raw materials. Pedestrian traffic &mdash; including funeral home drivers picking up orders &mdash; may be present in the yard. Forklift operators must be trained and authorized before operating any powered industrial truck on our property.",
        "discussion_questions": [
            "What is the first thing you do before operating a forklift each shift?",
            "A load feels unstable &mdash; what do you do?",
            "Where are the designated pedestrian walkways in our facility?",
        ],
    },
    {
        "filename": "safety_training_03_hazard_communication.pdf",
        "topic_title": "Hazard Communication and SDS",
        "osha_standard": "29 CFR 1910.1200",
        "osha_label": "Hazard Communication",
        "why_it_matters": "Workers have the right to know what chemicals they work with and what hazards those chemicals present. In a precast plant, you work with concrete admixtures, release agents, solvents, fuels, and other chemicals that can cause burns, respiratory problems, and long-term health effects if handled incorrectly.",
        "key_points": [
            "Every chemical in your workplace has a Safety Data Sheet (SDS) &mdash; it tells you the hazards, safe handling, and emergency response",
            "GHS labels on containers have a signal word (Danger or Warning), pictograms, and hazard statements &mdash; read them before using a product",
            "SDS documents are located at [LOCATION &mdash; FILL IN] and must be accessible at all times",
            "If you are exposed to a chemical &mdash; flush with water, find the SDS, and report the exposure",
            "Never transfer chemicals to unlabeled containers",
            "Dispose of chemical waste according to the instructions on the SDS &mdash; never pour down drains",
        ],
        "in_our_facility": "Chemicals used regularly include concrete release agents, form oil, admixtures, and cleaning solvents. The SDS binder contains a sheet for every chemical on our approved list. If you see a chemical without a label, report it to your supervisor immediately.",
        "discussion_questions": [
            "Where is the SDS binder/station in your work area?",
            "What does the corrosion pictogram (melting hand and surface) mean?",
            "Who do you call if there is a chemical spill?",
        ],
    },
    {
        "filename": "safety_training_04_ppe.pdf",
        "topic_title": "Personal Protective Equipment (PPE)",
        "osha_standard": "29 CFR 1910.132-138",
        "osha_label": "Personal Protective Equipment",
        "why_it_matters": "PPE is your last line of defense against workplace hazards. In a precast plant, flying concrete fragments, loud machinery, heavy falling objects, and chemical splashes are everyday hazards that PPE is designed to protect against.",
        "key_points": [
            "Hard hats are required in all production and yard areas &mdash; inspect yours for cracks or dents before each shift",
            "Safety glasses or face shields are required when cutting, grinding, chipping, or working with chemicals",
            "Hearing protection is required in areas posted as high noise",
            "Steel-toed boots are required in all production and yard areas",
            "Gloves appropriate for the task &mdash; leather for material handling, chemical-resistant for admixtures",
            "Replace damaged or worn PPE immediately &mdash; do not wait until it fails completely",
        ],
        "in_our_facility": "Required PPE for each area of our facility is posted at the entrance to that area. Replacement PPE is available from [LOCATION &mdash; FILL IN]. If your PPE is damaged, bring it to your supervisor &mdash; it will be replaced at no cost to you.",
        "discussion_questions": [
            "What PPE is required in the production yard?",
            "How do you know when a hard hat needs to be replaced?",
            "Where do you get replacement PPE if yours is damaged?",
        ],
    },
    {
        "filename": "safety_training_05_electrical_safety.pdf",
        "topic_title": "Electrical Safety and Arc Flash Awareness",
        "osha_standard": "29 CFR 1910.303-333",
        "osha_label": "Electrical Safety",
        "why_it_matters": "Electrocution is one of OSHA's Fatal Four hazards. In a precast plant, mixers, vibrators, compressors, and production equipment all involve electrical systems. Even low-voltage electricity can kill under the wrong conditions.",
        "key_points": [
            "Only qualified, authorized electricians may work on electrical equipment &mdash; never attempt electrical repairs yourself",
            "If you see damaged wiring, a sparking outlet, or a burning smell &mdash; report it immediately and keep others away",
            "Never use damaged extension cords or bypass safety devices like circuit breakers and GFCIs",
            "Water and electricity are fatal &mdash; keep electrical equipment dry and report any leaks near electrical panels",
            "Lockout/Tagout applies to electrical energy &mdash; all electrical work requires the circuit to be de-energized and locked out first",
            "Arc flash is an explosive release of energy from electrical equipment &mdash; stay out of marked arc flash boundaries",
        ],
        "in_our_facility": "Electrical panels are located at [LOCATION &mdash; FILL IN]. Only maintenance staff with electrical training are authorized to open panels or work on equipment electrical systems. All other staff must report electrical concerns to a supervisor.",
        "discussion_questions": [
            "Who is authorized to work on electrical equipment in our facility?",
            "What should you do if you see a damaged extension cord?",
            "Why should you never bypass a circuit breaker?",
        ],
    },
    {
        "filename": "safety_training_06_hearing_conservation.pdf",
        "topic_title": "Hearing Conservation",
        "osha_standard": "29 CFR 1910.95",
        "osha_label": "Occupational Noise Exposure",
        "why_it_matters": "Noise-induced hearing loss is permanent and painless until it is too late. Precast concrete manufacturing &mdash; mixers, vibrators, compressors, grinders, and impact tools &mdash; regularly produces noise at levels that cause hearing damage with repeated exposure.",
        "key_points": [
            "Hearing protection is required in areas where noise exceeds 85 decibels &mdash; these areas are posted",
            "Foam earplugs must be rolled thin, inserted deep, and held until they expand to form a seal",
            "Earmuffs must form a complete seal around both ears &mdash; glasses frames and hair can break the seal",
            "Double protection (earplugs plus earmuffs) is required for the loudest operations such as chipping and grinding",
            "Signs of hearing damage: ringing in your ears after work, asking people to repeat themselves more often",
            "Audiometric (hearing) testing is offered annually &mdash; take advantage of it",
        ],
        "in_our_facility": "High-noise areas are marked with yellow hearing protection required signs. If you are unsure whether an area requires protection, ask your supervisor or wear protection as a precaution. Disposable earplugs are available at [LOCATION &mdash; FILL IN].",
        "discussion_questions": [
            "Which areas of our facility require hearing protection?",
            "How do you know if your foam earplugs are inserted correctly?",
            "What does ringing in your ears after your shift indicate?",
        ],
    },
    {
        "filename": "safety_training_07_heat_illness_prevention.pdf",
        "topic_title": "Heat Illness Prevention",
        "osha_standard": "OSHA General Duty Clause Section 5(a)(1)",
        "osha_label": "Heat Illness Prevention",
        "why_it_matters": "Heat stroke can be fatal within minutes. Outdoor precast yard work and hot production areas during summer months create serious heat illness risk, especially during heat waves and for workers not yet acclimatized to hot conditions.",
        "key_points": [
            "Drink water every 15-20 minutes in hot conditions &mdash; do not wait until you are thirsty",
            "Rest in shade or cool areas during breaks &mdash; heat continues to build in your body if you do not cool down",
            "New workers and those returning from time off need 7-14 days to acclimatize &mdash; lighter duties initially",
            "Heat exhaustion warning signs: heavy sweating, weakness, cold/pale/clammy skin, nausea, headache",
            "Heat stroke is an emergency &mdash; confusion, hot/red/dry skin, no sweating, rapid pulse &mdash; call 911 immediately",
            "Watch your coworkers &mdash; people suffering heat stroke often cannot recognize it themselves",
        ],
        "in_our_facility": "Water and shade are provided in the production yard. During heat advisories, additional rest breaks will be scheduled. If you feel unwell due to heat &mdash; stop work and tell your supervisor immediately. Waiting makes it worse.",
        "discussion_questions": [
            "What is the first sign that a coworker may be developing heat exhaustion?",
            "How much water should you drink per hour in hot conditions?",
            "A coworker is confused, has stopped sweating, and has hot red skin &mdash; what do you do?",
        ],
    },
    {
        "filename": "safety_training_08_crane_rigging_safety.pdf",
        "topic_title": "Crane and Rigging Safety",
        "osha_standard": "29 CFR 1910.179",
        "osha_label": "Overhead and Gantry Cranes",
        "why_it_matters": "A dropped precast load can crush and kill instantly. Overhead crane failures and rigging failures are among the most serious hazards in a precast plant. This training applies to everyone who works in areas where lifts occur.",
        "key_points": [
            "Inspect all rigging equipment before use &mdash; damaged slings, hooks, or shackles must be removed from service",
            "Never exceed the rated capacity of the crane or any rigging component &mdash; the weakest link determines the safe load",
            "Keep people out of the load path &mdash; never stand under a suspended load for any reason",
            "Standard crane hand signals must be used when verbal communication is not possible &mdash; know the emergency stop signal",
            "Inspect wire rope for broken wires, kinking, or corrosion &mdash; 10 broken wires in any rope lay means remove from service",
            "Tag lines must be used to control loads &mdash; never use your hands to guide a swinging load",
        ],
        "in_our_facility": "Our overhead crane is rated at [CAPACITY &mdash; FILL IN] tons. Only trained and authorized operators may operate the crane. All other employees must stay clear of the lift zone during operations. The emergency stop signal is two clenched fists held together.",
        "discussion_questions": [
            "You notice a wire rope sling has several broken wires &mdash; what do you do?",
            "How do you signal an emergency stop to a crane operator?",
            "Why is it dangerous to stand under a raised load even briefly?",
        ],
    },
    {
        "filename": "safety_training_09_bloodborne_pathogens.pdf",
        "topic_title": "Bloodborne Pathogens and First Aid",
        "osha_standard": "29 CFR 1910.1030",
        "osha_label": "Bloodborne Pathogens",
        "why_it_matters": "Workplace injuries happen. When they do, a proper first aid response can prevent infection, reduce injury severity, and save lives. Understanding bloodborne pathogens protects both the injured worker and the person helping them.",
        "key_points": [
            "Treat all blood and bodily fluids as potentially infectious &mdash; put on gloves before providing first aid",
            "Standard precautions apply every time &mdash; you cannot tell by looking whether blood contains pathogens",
            "First aid kits are located at [LOCATION &mdash; FILL IN] &mdash; know where they are before an emergency",
            "For serious injuries &mdash; call 911 first, then provide first aid until emergency services arrive",
            "After any contact with blood &mdash; wash hands thoroughly with soap and water for at least 20 seconds",
            "Report all exposures to blood or bodily fluids to your supervisor immediately",
        ],
        "in_our_facility": "First aid kits are inspected monthly and restocked as needed. Employees trained in CPR and first aid are posted at the first aid station. Any employee who provides first aid assistance will be offered medical evaluation at no cost.",
        "discussion_questions": [
            "Where are the first aid kits in our facility?",
            "What do you put on before helping an injured coworker?",
            "You receive a deep cut and a coworker helps you &mdash; what should both of you do afterward?",
        ],
    },
    {
        "filename": "safety_training_10_fall_protection.pdf",
        "topic_title": "Fall Protection and Ladder Safety",
        "osha_standard": "29 CFR 1926.502",
        "osha_label": "Fall Protection",
        "why_it_matters": "Falls are the leading cause of death in construction and a major cause in general industry. In a precast facility, loading docks, elevated platforms, roof access points, and product storage areas all present fall hazards.",
        "key_points": [
            "Fall protection is required at heights of 4 feet or more in general industry &mdash; do not assume a short fall is safe",
            "Inspect ladders before use &mdash; cracked side rails, missing rungs, or damaged feet mean the ladder is out of service",
            "Extension ladders: set at a 4:1 angle (1 foot out for every 4 feet of height), extend 3 feet above the landing",
            "Three points of contact at all times on a ladder &mdash; two hands and one foot or two feet and one hand",
            "Never carry tools or materials in your hands while climbing &mdash; use a tool belt or hoisting line",
            "Guardrails, covers, and personal fall arrest systems must not be removed or bypassed",
        ],
        "in_our_facility": "Elevated work areas in our facility include loading docks, mold storage areas, and roof access points. Ladders are stored at [LOCATION &mdash; FILL IN]. If you identify a fall hazard &mdash; an open floor hole, a missing guardrail, an unsecured edge &mdash; report it immediately and block access if possible.",
        "discussion_questions": [
            "At what height does fall protection become required in general industry?",
            "How do you check that an extension ladder is at the correct angle?",
            "You find a portable ladder with a cracked side rail &mdash; what do you do with it?",
        ],
    },
    {
        "filename": "safety_training_11_confined_space.pdf",
        "topic_title": "Confined Space Awareness",
        "osha_standard": "29 CFR 1910.146",
        "osha_label": "Permit-Required Confined Spaces",
        "why_it_matters": "More than 60% of confined space fatalities are would-be rescuers &mdash; people who entered to help without proper equipment and were overcome by the same hazard. In a precast plant, tanks, pits, large forms, and enclosed equipment can qualify as confined spaces.",
        "key_points": [
            "A confined space is any space large enough to enter, with limited entry/exit, and not designed for continuous occupancy",
            "A permit-required confined space has atmospheric hazards, engulfment risk, or configuration hazards &mdash; entry requires a permit",
            "Never enter a permit-required confined space without a completed entry permit, atmospheric testing, and an attendant outside",
            "The attendant must never enter the space to attempt rescue &mdash; call for trained rescue personnel",
            "Oxygen deficiency (below 19.5%) and toxic gases can incapacitate without warning &mdash; you cannot see or smell them",
            "If you find someone collapsed in a confined space &mdash; call for help first, do not enter",
        ],
        "in_our_facility": "Potential confined spaces in our facility include [SPECIFIC TANKS, PITS, OR FORMS &mdash; FILL IN]. Confined space entry permits are obtained from [SUPERVISOR/SAFETY MANAGER &mdash; FILL IN]. Any space that you are unsure about should be treated as permit-required until evaluated.",
        "discussion_questions": [
            "Can you name a potential confined space in our facility?",
            "A coworker enters a tank and collapses &mdash; what is the first thing you do?",
            "Why is it so dangerous to enter a confined space to rescue someone without proper equipment?",
        ],
    },
    {
        "filename": "safety_training_12_emergency_action_fire.pdf",
        "topic_title": "Emergency Action Plans and Fire Safety",
        "osha_standard": "29 CFR 1910.38",
        "osha_label": "Emergency Action Plans",
        "why_it_matters": "Knowing what to do before an emergency happens is the difference between an orderly evacuation and a chaotic one. Every person in your facility should know the evacuation routes, assembly points, and who to call without having to think about it.",
        "key_points": [
            "The emergency assembly point is at [LOCATION &mdash; FILL IN] &mdash; go there immediately upon hearing the alarm",
            "Do not stop to collect personal belongings during an evacuation &mdash; leave immediately",
            "Fire extinguisher use &mdash; PASS: Pull the pin, Aim at the base, Squeeze the handle, Sweep side to side",
            "Only attempt to fight a small, contained fire if you are trained and have a clear exit path &mdash; otherwise evacuate",
            "Know who to call: fire/medical/police: 911 &middot; Facility emergency contact: [NAME AND NUMBER &mdash; FILL IN]",
            "Severe weather shelter location: [LOCATION &mdash; FILL IN]",
        ],
        "in_our_facility": "Evacuation route maps are posted at [LOCATIONS &mdash; FILL IN]. Fire extinguishers are inspected monthly and tagged with the inspection date. The designated fire wardens for our facility are [NAMES &mdash; FILL IN]. During an emergency, do not use elevators.",
        "discussion_questions": [
            "Where is our emergency assembly point?",
            "What does PASS stand for when using a fire extinguisher?",
            "You discover a small fire in a trash can near the exit &mdash; what do you do?",
        ],
    },
]

# ── Lookup by topic_key ──────────────────────────────────────────────────────
TOPIC_DATA = {t["filename"].split("_", 3)[-1].replace(".pdf", ""): t for t in TRAININGS}
# Also index by the actual topic_key pattern used in the database
for t in TRAININGS:
    # Extract topic key from filename: safety_training_01_lockout_tagout.pdf -> lockout_tagout
    parts = t["filename"].replace(".pdf", "").split("_", 3)
    if len(parts) >= 4:
        TOPIC_DATA[parts[3]] = t


# N/A alternative text for fields where equipment/feature doesn't exist
NA_TEXT = {
    "overhead_crane": (
        "This facility does not operate overhead cranes. "
        "If you encounter crane operations at any work site, "
        "do not approach the lift zone and contact your "
        "supervisor for site-specific procedures."
    ),
    "confined_spaces": (
        "This facility does not currently have permit-required "
        "confined spaces. If you encounter a space at any work "
        "site that may qualify as a confined space &mdash; enclosed, "
        "limited entry, not designed for continuous occupancy &mdash; "
        "treat it as permit-required and contact your supervisor "
        "before entering under any circumstances."
    ),
    "confined_space_permit": (
        "Contact your supervisor before any confined space entry."
    ),
    "forklift": (
        "This facility does not currently operate forklifts or "
        "powered industrial trucks. If you work at a site where "
        "forklifts operate, maintain a safe distance, use "
        "designated pedestrian walkways, and make eye contact "
        "with operators before crossing travel paths."
    ),
    "pedestrian_walkways": (
        "Remain aware of vehicle traffic in all work areas "
        "and make eye contact with equipment operators before "
        "crossing any travel path."
    ),
    "electrical_panels": (
        "All electrical panel access and electrical work at "
        "this facility is performed by licensed contractors. "
        "Employees must never open electrical panels or attempt "
        "electrical repairs. Report any electrical concerns to "
        "your supervisor immediately."
    ),
}


def fill_placeholders(text: str, details: dict) -> str:
    """Replace [PLACEHOLDER] strings with facility-specific values or N/A text."""
    replacements = {
        # Always-applicable fields
        "[COMPANY NAME]": details.get("company_name", "[COMPANY NAME]"),
        "[LOCATION &mdash; FILL IN]": details.get("_generic_location", "[LOCATION &mdash; FILL IN]"),
        "[LOTO DEVICE LOCATION &mdash; FILL IN]": details.get("loto_device_location", "[LOCATION &mdash; FILL IN]"),
        "[SDS LOCATION &mdash; FILL IN]": " and ".join(details.get("sds_locations", [])) or "[LOCATION &mdash; FILL IN]",
        "[PPE REPLACEMENT LOCATION &mdash; FILL IN]": details.get("ppe_replacement_location", "[LOCATION &mdash; FILL IN]"),
        "[EARPLUG LOCATION &mdash; FILL IN]": details.get("earplug_dispenser_location", "[LOCATION &mdash; FILL IN]"),
        "[FIRST AID KIT LOCATIONS &mdash; FILL IN]": " and ".join(details.get("first_aid_kit_locations", [])) or "[LOCATION &mdash; FILL IN]",
        "[FIRST AID TRAINED &mdash; FILL IN]": ", ".join(details.get("first_aid_trained_employees", [])) or "posted at the first aid station",
        "[LADDER STORAGE &mdash; FILL IN]": details.get("ladder_storage_location", "[LOCATION &mdash; FILL IN]"),
        "[ASSEMBLY POINT &mdash; FILL IN]": details.get("assembly_point", "[ASSEMBLY POINT &mdash; FILL IN]"),
        "[SEVERE WEATHER SHELTER &mdash; FILL IN]": details.get("severe_weather_shelter", "[SHELTER LOCATION &mdash; FILL IN]"),
        "[LOCATIONS &mdash; FILL IN]": details.get("evacuation_map_locations", "[LOCATIONS &mdash; FILL IN]"),
        "[NAMES &mdash; FILL IN]": " and ".join(details.get("fire_wardens", [])) or "[FIRE WARDENS &mdash; FILL IN]",
        "[NAME AND NUMBER &mdash; FILL IN]": (
            f"{details.get('emergency_contact_name', '')} &middot; {details.get('emergency_contact_phone', '')}"
            if details.get("emergency_contact_name")
            else "[EMERGENCY CONTACT &mdash; FILL IN]"
        ),
        # N/A-capable fields
        "[CAPACITY &mdash; FILL IN]": (
            NA_TEXT["overhead_crane"]
            if details.get("overhead_crane_not_applicable")
            else (
                f"{details['overhead_crane_capacity']} tons"
                if details.get("overhead_crane_capacity")
                else "[CAPACITY &mdash; FILL IN]"
            )
        ),
        "[SPECIFIC TANKS, PITS, OR FORMS &mdash; FILL IN]": (
            NA_TEXT["confined_spaces"]
            if details.get("confined_spaces_not_applicable")
            else ", ".join(details.get("confined_spaces", [])) or "[LOCATIONS &mdash; FILL IN]"
        ),
        "[SUPERVISOR/SAFETY MANAGER &mdash; FILL IN]": (
            NA_TEXT["confined_space_permit"]
            if details.get("confined_spaces_not_applicable")
            else details.get("confined_space_permit_issuer", "[NAME/TITLE &mdash; FILL IN]")
        ),
        "[ELECTRICAL PANEL LOCATION &mdash; FILL IN]": (
            NA_TEXT["electrical_panels"]
            if details.get("electrical_panels_not_applicable")
            else ", ".join(details.get("electrical_panel_locations", [])) or "[LOCATION &mdash; FILL IN]"
        ),
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def generate_personalized(topic_key: str, output_path: str, details: dict) -> None:
    """Generate a personalized PDF for a specific topic with facility details."""
    topic = TOPIC_DATA.get(topic_key)
    if not topic:
        print(f"Unknown topic_key: {topic_key}")
        return

    personalized = {
        **topic,
        "filename": output_path,
        "why_it_matters": fill_placeholders(topic["why_it_matters"], details),
        "in_our_facility": fill_placeholders(topic["in_our_facility"], details),
        "key_points": [fill_placeholders(p, details) for p in topic["key_points"]],
        "discussion_questions": [fill_placeholders(q, details) for q in topic["discussion_questions"]],
    }
    # Override company name in the PDF header
    if details.get("company_name"):
        personalized["_company_name"] = details["company_name"]

    build_pdf(**personalized)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        # Personalized generation mode
        params = json.loads(sys.argv[1])
        generate_personalized(
            params["topic_key"],
            params["output_path"],
            params.get("details", {}),
        )
    else:
        # Default: generate all 12 platform defaults
        print(f"Generating {len(TRAININGS)} safety training PDFs...")
        for training in TRAININGS:
            build_pdf(**training)
        print(f"\nAll {len(TRAININGS)} PDFs generated in: {OUTPUT_DIR}")
