"""Default workflow definitions — Tier 2 defaults shipped with the platform.

Seeded via seed_default_workflows on migration. Idempotent by workflow id.
"""

MANUFACTURING_WORKFLOWS = [
    {
        "id": "wf_mfg_disinterment",
        "name": "Start Disinterment Workflow",
        "description": "Begin a disinterment order for a funeral home",
        "keywords": ["disinterment", "dis", "start disinterment", "new disinterment", "exhumation"],
        "tier": 2,
        "vertical": "manufacturing",
        "trigger_type": "manual",
        "icon": "clipboard-list",
        "command_bar_priority": 90,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "ask_funeral_home",
                "step_type": "input",
                "config": {
                    "prompt": "Which funeral home?",
                    "input_type": "crm_search",
                    "crm_filter": {"is_funeral_home": True},
                    "required": True,
                    "placeholder": "Search funeral homes...",
                },
            },
            {
                "step_order": 2,
                "step_key": "create_disinterment",
                "step_type": "action",
                "config": {
                    "action_type": "create_record",
                    "record_type": "disinterment_order",
                    "fields": {
                        "funeral_home_id": "{input.ask_funeral_home.id}",
                        "funeral_home_name": "{input.ask_funeral_home.name}",
                        "status": "pending",
                    },
                },
            },
            {
                "step_order": 3,
                "step_key": "open_order",
                "step_type": "output",
                "config": {
                    "action_type": "open_slide_over",
                    "record_type": "disinterment_order",
                    "record_id": "{output.create_disinterment.id}",
                    "mode": "edit",
                },
            },
        ],
    },
    {
        "id": "wf_mfg_create_order",
        "name": "Create Order",
        "description": "Create a new vault order for a customer",
        "keywords": ["create order", "new order", "order for", "add order", "place order"],
        "tier": 2,
        "vertical": "manufacturing",
        "trigger_type": "manual",
        "icon": "plus-circle",
        "command_bar_priority": 95,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "ask_customer",
                "step_type": "input",
                "config": {
                    "prompt": "Which customer?",
                    "input_type": "crm_search",
                    "required": True,
                    "placeholder": "Search customers...",
                },
            },
            {
                "step_order": 2,
                "step_key": "create_order",
                "step_type": "action",
                "config": {
                    "action_type": "create_record",
                    "record_type": "order",
                    "fields": {
                        "company_entity_id": "{input.ask_customer.id}",
                        "customer_name": "{input.ask_customer.name}",
                        "status": "pending",
                    },
                },
            },
            {
                "step_order": 3,
                "step_key": "open_order",
                "step_type": "output",
                "config": {
                    "action_type": "open_slide_over",
                    "record_type": "order",
                    "record_id": "{output.create_order.id}",
                    "mode": "edit",
                },
            },
        ],
    },
    {
        "id": "wf_mfg_schedule_delivery",
        "name": "Schedule Delivery",
        "description": "Schedule a delivery for an existing order",
        "keywords": ["schedule delivery", "delivery", "deliver", "schedule", "add delivery"],
        "tier": 2,
        "vertical": "manufacturing",
        "trigger_type": "manual",
        "icon": "truck",
        "command_bar_priority": 85,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "ask_order",
                "step_type": "input",
                "config": {
                    "prompt": "Which order?",
                    "input_type": "record_search",
                    "record_type": "order",
                    "filter": {"status": ["confirmed", "pending"]},
                    "required": True,
                },
            },
            {
                "step_order": 2,
                "step_key": "ask_date",
                "step_type": "input",
                "config": {
                    "prompt": "Delivery date?",
                    "input_type": "date_picker",
                    "required": True,
                    "min_date": "today",
                },
            },
            {
                "step_order": 3,
                "step_key": "create_delivery",
                "step_type": "action",
                "config": {
                    "action_type": "create_record",
                    "record_type": "delivery",
                    "fields": {
                        "order_id": "{input.ask_order.id}",
                        "scheduled_date": "{input.ask_date}",
                        "status": "scheduled",
                    },
                },
            },
            {
                "step_order": 4,
                "step_key": "open_delivery",
                "step_type": "output",
                "config": {
                    "action_type": "open_slide_over",
                    "record_type": "delivery",
                    "record_id": "{output.create_delivery.id}",
                    "mode": "edit",
                },
            },
        ],
    },
    {
        "id": "wf_mfg_log_pour",
        "name": "Log Production Pour",
        "description": "Record a vault production pour",
        "keywords": ["log pour", "pour", "log production", "production pour", "poured"],
        "tier": 2,
        "vertical": "manufacturing",
        "trigger_type": "manual",
        "icon": "layers",
        "command_bar_priority": 80,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "ask_product",
                "step_type": "input",
                "config": {
                    "prompt": "Which product?",
                    "input_type": "record_search",
                    "record_type": "product",
                    "required": True,
                },
            },
            {
                "step_order": 2,
                "step_key": "ask_quantity",
                "step_type": "input",
                "config": {
                    "prompt": "How many units poured?",
                    "input_type": "number",
                    "min": 1,
                    "required": True,
                },
            },
            {
                "step_order": 3,
                "step_key": "log_pour",
                "step_type": "action",
                "config": {
                    "action_type": "log_vault_item",
                    "item_type": "event",
                    "event_type": "production_pour",
                    "title": "{input.ask_quantity} x {input.ask_product.name}",
                    "metadata": {
                        "product_id": "{input.ask_product.id}",
                        "product_name": "{input.ask_product.name}",
                        "quantity": "{input.ask_quantity}",
                    },
                },
            },
            {
                "step_order": 4,
                "step_key": "confirm",
                "step_type": "output",
                "config": {
                    "action_type": "show_confirmation",
                    "message": "Pour logged: {input.ask_quantity} x {input.ask_product.name}",
                },
            },
        ],
    },
    {
        "id": "wf_mfg_send_statement",
        "name": "Send Statement",
        "description": "Generate and email a statement to a customer",
        "keywords": ["send statement", "statement", "monthly statement", "email statement", "ar statement"],
        "tier": 2,
        "vertical": "manufacturing",
        "trigger_type": "manual",
        "icon": "file-text",
        "command_bar_priority": 75,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "ask_customer",
                "step_type": "input",
                "config": {
                    "prompt": "Which customer?",
                    "input_type": "crm_search",
                    "required": True,
                },
            },
            {
                "step_order": 2,
                "step_key": "generate_statement",
                "step_type": "action",
                "config": {
                    "action_type": "generate_document",
                    "document_type": "statement",
                    "company_entity_id": "{input.ask_customer.id}",
                },
            },
            {
                "step_order": 3,
                "step_key": "send_email",
                "step_type": "action",
                "config": {
                    "action_type": "send_email",
                    "to": "{input.ask_customer.primary_email}",
                    "subject": "Your statement from {current_company.name}",
                    "template": "statement_email",
                },
            },
            {
                "step_order": 4,
                "step_key": "confirm",
                "step_type": "output",
                "config": {
                    "action_type": "show_confirmation",
                    "message": "Statement sent to {input.ask_customer.name}",
                },
            },
        ],
    },
    {
        "id": "wf_mfg_eod_delivery_reminder",
        "name": "End of Day Delivery Review",
        "description": "Daily reminder to review tomorrow's deliveries",
        "keywords": [],   # time-triggered only
        "tier": 3,        # default OFF
        "vertical": "manufacturing",
        "trigger_type": "time_of_day",
        "trigger_config": {
            "time": "17:00",
            "days": ["mon", "tue", "wed", "thu", "fri"],
            "timezone": "company",
        },
        "icon": "clock",
        "command_bar_priority": 0,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "notify_admin",
                "step_type": "action",
                "config": {
                    "action_type": "send_notification",
                    "notify_roles": ["admin", "office"],
                    "title": "Review tomorrow's deliveries",
                    "body": "Check the scheduling board for tomorrow's stops.",
                    "link": "/scheduling",
                },
            },
        ],
    },
]


FUNERAL_HOME_WORKFLOWS = [
    {
        "id": "wf_fh_first_call",
        "name": "First Call Intake",
        "description": "Create a new case from a first call",
        "keywords": ["first call", "new call", "new case", "intake", "family called", "death call"],
        "tier": 2,
        "vertical": "funeral_home",
        "trigger_type": "manual",
        "icon": "phone",
        "command_bar_priority": 100,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "ask_disposition",
                "step_type": "input",
                "config": {
                    "prompt": "Burial or cremation?",
                    "input_type": "select",
                    "options": [
                        {"value": "burial", "label": "Traditional Burial"},
                        {"value": "cremation", "label": "Cremation"},
                        {"value": "cremation_with_service", "label": "Cremation with Memorial Service"},
                        {"value": "undecided", "label": "Undecided"},
                    ],
                    "required": True,
                },
            },
            {
                "step_order": 2,
                "step_key": "ask_director",
                "step_type": "input",
                "config": {
                    "prompt": "Assign to which director?",
                    "input_type": "user_search",
                    "user_filter": {"roles": ["director", "admin"]},
                    "default": "current_user",
                    "required": True,
                },
            },
            {
                "step_order": 3,
                "step_key": "create_case",
                "step_type": "action",
                "config": {
                    "action_type": "create_record",
                    "record_type": "funeral_case",
                    "fields": {
                        "director_id": "{input.ask_director.id}",
                        "status": "active",
                    },
                },
            },
            {
                "step_order": 4,
                "step_key": "notify_director",
                "step_type": "action",
                "config": {
                    "action_type": "send_notification",
                    "notify_user_id": "{input.ask_director.id}",
                    "title": "New case assigned",
                    "body": "A new case has been assigned to you.",
                    "link": "/fh/cases/{output.create_case.id}",
                },
            },
            {
                "step_order": 5,
                "step_key": "open_case",
                "step_type": "output",
                "config": {
                    "action_type": "open_slide_over",
                    "record_type": "funeral_case",
                    "record_id": "{output.create_case.id}",
                    "mode": "edit",
                },
            },
        ],
    },
    {
        "id": "wf_fh_schedule_arrangement",
        "name": "Schedule Arrangement Conference",
        "description": "Schedule an arrangement conference for a family",
        "keywords": ["schedule arrangement", "arrangement conference", "book arrangement", "arrangement appointment"],
        "tier": 2,
        "vertical": "funeral_home",
        "trigger_type": "manual",
        "icon": "calendar",
        "command_bar_priority": 90,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "ask_case",
                "step_type": "input",
                "config": {
                    "prompt": "Which case?",
                    "input_type": "record_search",
                    "record_type": "funeral_case",
                    "filter": {"status": "active"},
                    "required": True,
                },
            },
            {
                "step_order": 2,
                "step_key": "ask_datetime",
                "step_type": "input",
                "config": {
                    "prompt": "When is the arrangement conference?",
                    "input_type": "datetime_picker",
                    "required": True,
                    "min_date": "today",
                },
            },
            {
                "step_order": 3,
                "step_key": "log_event",
                "step_type": "action",
                "config": {
                    "action_type": "log_vault_item",
                    "item_type": "event",
                    "event_type": "arrangement_conference",
                    "related_entity_type": "funeral_case",
                    "related_entity_id": "{input.ask_case.id}",
                    "title": "Arrangement Conference — {input.ask_case.deceased_name}",
                    "metadata": {"scheduled_at": "{input.ask_datetime}"},
                },
            },
            {
                "step_order": 4,
                "step_key": "confirm",
                "step_type": "output",
                "config": {
                    "action_type": "show_confirmation",
                    "message": "Arrangement scheduled.",
                },
            },
        ],
    },
    {
        "id": "wf_fh_aftercare_7day",
        "name": "7-Day Aftercare Follow-Up",
        "description": "Send a care message to families 7 days after service",
        "keywords": [],
        "tier": 3,
        "vertical": "funeral_home",
        "trigger_type": "time_after_event",
        "trigger_config": {
            "record_type": "funeral_case",
            "field": "service_date",
            "offset_days": 7,
            "run_at_time": "10:00",
        },
        "icon": "heart",
        "command_bar_priority": 0,
        "is_system": True,
        "steps": [
            {
                "step_order": 1,
                "step_key": "send_message",
                "step_type": "action",
                "config": {
                    "action_type": "send_email",
                    "to": "{current_record.primary_contact_email}",
                    "subject": "We're thinking of you",
                    "template": "aftercare_7day",
                },
            },
            {
                "step_order": 2,
                "step_key": "log_event",
                "step_type": "action",
                "config": {
                    "action_type": "log_vault_item",
                    "item_type": "communication",
                    "event_type": "aftercare_message",
                    "related_entity_type": "funeral_case",
                    "related_entity_id": "{current_record.id}",
                    "title": "7-day aftercare message sent",
                },
            },
        ],
    },
]


ALL_DEFAULT_WORKFLOWS = MANUFACTURING_WORKFLOWS + FUNERAL_HOME_WORKFLOWS
