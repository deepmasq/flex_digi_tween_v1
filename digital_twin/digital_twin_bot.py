import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import asdict

from pymongo import AsyncMongoClient

from flexus_client_kit import ckit_client
from flexus_client_kit import ckit_cloudtool
from flexus_client_kit import ckit_bot_exec
from flexus_client_kit import ckit_shutdown
from flexus_client_kit import ckit_ask_model
from flexus_client_kit import ckit_mongo
from flexus_client_kit import ckit_kanban
from flexus_client_kit import ckit_external_auth
from flexus_client_kit.integrations import fi_mongo_store
from flexus_client_kit.integrations import fi_pdoc
from flexus_client_kit.integrations import fi_telegram
from flexus_client_kit.integrations import fi_gmail
from digital_twin import digital_twin_install

logger = logging.getLogger("bot_digital_twin")

BOT_NAME = "digital_twin"
BOT_VERSION = "0.1.0"

UPLOAD_DOCUMENT_TOOL = ckit_cloudtool.CloudTool(
    strict=True,
    name="upload_personality_document",
    description="Upload and process a document to extract personality traits, communication style, and knowledge. Supports PDF, Word docs, and text content.",
    parameters={
        "type": "object",
        "properties": {
            "doc_path": {"type": "string", "description": "Path to document in policy storage (e.g., /training/emails-2024)"},
            "doc_type": {"type": "string", "enum": ["emails", "writing", "memos", "chat", "other"], "description": "Type of document content"},
            "extract_focus": {"type": "string", "enum": ["style", "values", "knowledge", "all"], "description": "What to focus on extracting"},
        },
        "required": ["doc_path", "doc_type", "extract_focus"],
        "additionalProperties": False,
    },
)

GENERATE_RESPONSE_TOOL = ckit_cloudtool.CloudTool(
    strict=True,
    name="generate_twin_response",
    description="Generate a response in Art's voice based on the personality model and current context. Includes confidence scoring.",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The incoming message to respond to"},
            "context": {"type": ["string", "null"], "description": "Additional context (calendar, previous conversations, etc.)"},
            "urgency": {"type": "string", "enum": ["low", "medium", "high"], "description": "Message urgency level"},
        },
        "required": ["message", "context", "urgency"],
        "additionalProperties": False,
    },
)

NOTIFY_ART_TOOL = ckit_cloudtool.CloudTool(
    strict=True,
    name="notify_art",
    description="Notify Art about a conversation the digital twin handled. Sends via both Email and Telegram.",
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Brief summary of the conversation"},
            "requester": {"type": "string", "description": "Who initiated the conversation"},
            "twin_response": {"type": "string", "description": "What the twin said"},
            "needs_approval": {"type": "boolean", "description": "Whether this requires Art's approval before action"},
        },
        "required": ["summary", "requester", "twin_response", "needs_approval"],
        "additionalProperties": False,
    },
)

CHECK_CALENDAR_TOOL = ckit_cloudtool.CloudTool(
    strict=True,
    name="check_calendar",
    description="Check Art's Google Calendar for availability and current context.",
    parameters={
        "type": "object",
        "properties": {
            "timeframe": {"type": "string", "enum": ["now", "today", "this_week", "next_week"], "description": "What timeframe to check"},
            "purpose": {"type": "string", "enum": ["availability", "context", "schedule_meeting"], "description": "Why checking calendar"},
        },
        "required": ["timeframe", "purpose"],
        "additionalProperties": False,
    },
)

LEARN_CORRECTION_TOOL = ckit_cloudtool.CloudTool(
    strict=True,
    name="learn_from_correction",
    description="Process Art's correction to improve the personality model. Detects 'Actually I would say...' patterns.",
    parameters={
        "type": "object",
        "properties": {
            "original_response": {"type": "string", "description": "What the twin originally said"},
            "correct_response": {"type": "string", "description": "What Art says should have been said"},
            "context": {"type": "string", "description": "The original question/context"},
        },
        "required": ["original_response", "correct_response", "context"],
        "additionalProperties": False,
    },
)

PERSONALITY_MODEL_TOOL = ckit_cloudtool.CloudTool(
    strict=True,
    name="personality_model",
    description="Read or update the personality model stored as a policy document.",
    parameters={
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["read", "update"], "description": "Operation to perform"},
            "section": {"type": ["string", "null"], "description": "Which section to update: identity, communication_style, knowledge, values, relationships, rules (null for read op)"},
            "content": {"type": ["string", "null"], "description": "Content to add/update (for update op)"},
        },
        "required": ["op", "section", "content"],
        "additionalProperties": False,
    },
)

TOOLS = [
    UPLOAD_DOCUMENT_TOOL,
    GENERATE_RESPONSE_TOOL,
    NOTIFY_ART_TOOL,
    CHECK_CALENDAR_TOOL,
    LEARN_CORRECTION_TOOL,
    PERSONALITY_MODEL_TOOL,
    fi_mongo_store.MONGO_STORE_TOOL,
    fi_pdoc.POLICY_DOCUMENT_TOOL,
    fi_telegram.TELEGRAM_TOOL,
    fi_gmail.GMAIL_TOOL,
]


async def digital_twin_main_loop(fclient: ckit_client.FlexusClient, rcx: ckit_bot_exec.RobotContext) -> None:
    def get_setup():
        return ckit_bot_exec.official_setup_mixing_procedure(
            digital_twin_install.DIGITAL_TWIN_SETUP_SCHEMA,
            rcx.persona.persona_setup,
        )

    mongo_conn_str = await ckit_mongo.mongo_fetch_creds(fclient, rcx.persona.persona_id)
    mongo = AsyncMongoClient(mongo_conn_str)
    dbname = rcx.persona.persona_id + "_db"
    mydb = mongo[dbname]
    personal_mongo = mydb["personal_mongo"]
    conversations_collection = mydb["twin_conversations"]
    corrections_collection = mydb["twin_corrections"]

    pdoc_integration = fi_pdoc.IntegrationPdoc(rcx, rcx.persona.ws_root_group_id)
    gmail_integration = fi_gmail.IntegrationGmail(fclient, rcx)
    telegram = await fi_telegram.IntegrationTelegram.create(
        fclient,
        rcx,
        get_setup().get("TELEGRAM_BOT_TOKEN", ""),
    )

    @rcx.on_updated_message
    async def updated_message_in_db(msg: ckit_ask_model.FThreadMessageOutput):
        await telegram.look_assistant_might_have_posted_something(msg)

    @rcx.on_updated_thread
    async def updated_thread_in_db(th: ckit_ask_model.FThreadOutput):
        pass

    @rcx.on_updated_task
    async def updated_task_in_db(t: ckit_kanban.FPersonaKanbanTaskOutput):
        pass

    @rcx.on_emessage("TELEGRAM")
    async def handle_telegram_emessage(emsg):
        await telegram.handle_emessage(emsg)

    @rcx.on_tool_call(UPLOAD_DOCUMENT_TOOL.name)
    async def toolcall_upload_document(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        doc_path = model_args["doc_path"]
        doc_type = model_args["doc_type"]
        extract_focus = model_args["extract_focus"]

        result = await pdoc_integration.called_by_model(
            toolcall,
            {"op": "read", "path": doc_path},
        )

        if "ERROR" in result:
            return result

        subchats = await ckit_ask_model.bot_subchat_create_multiple(
            client=fclient,
            who_is_asking="digital_twin_extract",
            persona_id=rcx.persona.persona_id,
            first_question=[f"Extract {extract_focus} from document type {doc_type}:\n\n{result[:5000]}"],
            first_calls=["null"],
            title=[f"Processing {doc_path}"],
            fcall_id=toolcall.fcall_id,
            fexp_name="extractor",
        )
        raise ckit_cloudtool.WaitForSubchats(subchats)

    @rcx.on_tool_call(GENERATE_RESPONSE_TOOL.name)
    async def toolcall_generate_response(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        message = model_args["message"]
        context = model_args.get("context", "")
        urgency = model_args["urgency"]

        personality_result = await pdoc_integration.called_by_model(
            toolcall,
            {"op": "read", "path": "/personality/art_model"},
        )

        personality = personality_result if "ERROR" not in personality_result else "{}"

        subchats = await ckit_ask_model.bot_subchat_create_multiple(
            client=fclient,
            who_is_asking="digital_twin_respond",
            persona_id=rcx.persona.persona_id,
            first_question=[f"Generate response in Art's voice.\n\nPersonality Model:\n{personality[:3000]}\n\nContext: {context}\n\nMessage: {message}\n\nUrgency: {urgency}"],
            first_calls=["null"],
            title=["Generating response"],
            fcall_id=toolcall.fcall_id,
            fexp_name="responder",
        )
        raise ckit_cloudtool.WaitForSubchats(subchats)

    @rcx.on_tool_call(NOTIFY_ART_TOOL.name)
    async def toolcall_notify_art(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        summary = model_args["summary"]
        requester = model_args["requester"]
        twin_response = model_args["twin_response"]
        needs_approval = model_args["needs_approval"]

        setup = get_setup()
        art_email = setup.get("ART_EMAIL", "")
        art_telegram_chat_id = setup.get("ART_TELEGRAM_CHAT_ID", "")

        notification_text = f"🤖 Digital Twin Conversation\n\nFrom: {requester}\nSummary: {summary}\n\nTwin said:\n{twin_response}\n\n{'⚠️ NEEDS YOUR APPROVAL' if needs_approval else 'FYI only'}"

        results = []

        if art_telegram_chat_id and telegram:
            tg_result = await telegram.called_by_model(
                toolcall,
                {
                    "op": "post",
                    "chat_id": int(art_telegram_chat_id),
                    "message": notification_text,
                },
            )
            results.append(f"Telegram: {tg_result}")

        if art_email and gmail_integration:
            email_result = await gmail_integration.called_by_model(
                toolcall,
                {
                    "op": "send",
                    "to": art_email,
                    "subject": f"Digital Twin: {summary[:50]}",
                    "body": notification_text,
                },
            )
            results.append(f"Email: {email_result}")

        await conversations_collection.insert_one({
            "timestamp": time.time(),
            "requester": requester,
            "summary": summary,
            "twin_response": twin_response,
            "needs_approval": needs_approval,
        })

        return "\n".join(results) if results else "No notification channels configured"

    @rcx.on_tool_call(CHECK_CALENDAR_TOOL.name)
    async def toolcall_check_calendar(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        timeframe = model_args["timeframe"]
        purpose = model_args["purpose"]

        return f"Calendar integration pending - would check {timeframe} for {purpose}. Requires Google Calendar API OAuth setup."

    @rcx.on_tool_call(LEARN_CORRECTION_TOOL.name)
    async def toolcall_learn_correction(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        original = model_args["original_response"]
        correct = model_args["correct_response"]
        context = model_args["context"]

        await corrections_collection.insert_one({
            "timestamp": time.time(),
            "original_response": original,
            "correct_response": correct,
            "context": context,
            "processed": False,
        })

        subchats = await ckit_ask_model.bot_subchat_create_multiple(
            client=fclient,
            who_is_asking="digital_twin_learn",
            persona_id=rcx.persona.persona_id,
            first_question=[f"Analyze correction and extract learning.\n\nContext: {context}\n\nTwin said: {original}\n\nArt says: {correct}"],
            first_calls=["null"],
            title=["Learning from correction"],
            fcall_id=toolcall.fcall_id,
            fexp_name="learner",
        )
        raise ckit_cloudtool.WaitForSubchats(subchats)

    @rcx.on_tool_call(PERSONALITY_MODEL_TOOL.name)
    async def toolcall_personality_model(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        op = model_args["op"]
        section = model_args.get("section")
        content = model_args.get("content")

        if op == "read":
            return await pdoc_integration.called_by_model(
                toolcall,
                {"op": "read", "path": "/personality/art_model"},
            )
        elif op == "update":
            current = await pdoc_integration.called_by_model(
                toolcall,
                {"op": "read", "path": "/personality/art_model"},
            )

            if "ERROR" in current:
                model_doc = {"personality_model": {"meta": {"created_at": time.strftime("%Y-%m-%d %H:%M:%S")}}}
            else:
                try:
                    model_doc = json.loads(current)
                except:
                    model_doc = {"personality_model": {"meta": {"created_at": time.strftime("%Y-%m-%d %H:%M:%S")}}}

            if section and content:
                model_doc["personality_model"][section] = content

            return await pdoc_integration.called_by_model(
                toolcall,
                {"op": "write", "path": "/personality/art_model", "content": json.dumps(model_doc, indent=2)},
            )

        return "Unknown operation"

    @rcx.on_tool_call(fi_mongo_store.MONGO_STORE_TOOL.name)
    async def toolcall_mongo_store(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        return await fi_mongo_store.handle_mongo_store(
            rcx.workdir,
            personal_mongo,
            toolcall,
            model_args,
        )

    @rcx.on_tool_call(fi_pdoc.POLICY_DOCUMENT_TOOL.name)
    async def toolcall_pdoc(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        return await pdoc_integration.called_by_model(toolcall, model_args)

    @rcx.on_tool_call(fi_telegram.TELEGRAM_TOOL.name)
    async def toolcall_telegram(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        return await telegram.called_by_model(toolcall, model_args)

    @rcx.on_tool_call(fi_gmail.GMAIL_TOOL.name)
    async def toolcall_gmail(toolcall: ckit_cloudtool.FCloudtoolCall, model_args: Dict[str, Any]) -> str:
        return await gmail_integration.called_by_model(toolcall, model_args)

    async def telegram_activity_callback(a: fi_telegram.ActivityTelegram, already_posted: bool):
        logger.info("%s Telegram message from @%s: %s", rcx.persona.persona_id, a.message_author_name, a.message_text[:50])
        if already_posted:
            return

        if "actually i would say" in a.message_text.lower():
            title = f"⚠️ CORRECTION from Art: {a.message_text[:100]}"
        else:
            title = f"Digital Twin request from @{a.message_author_name}: {a.message_text[:100]}"

        await ckit_kanban.bot_kanban_post_into_inbox(
            fclient,
            rcx.persona.persona_id,
            title=title,
            details_json=json.dumps(asdict(a)),
            provenance_message="digital_twin_telegram",
            fexp_name="default",
        )

    telegram.set_activity_callback(telegram_activity_callback)

    try:
        while not ckit_shutdown.shutdown_event.is_set():
            await rcx.unpark_collected_events(sleep_if_no_work=10.0)

    finally:
        await telegram.close()
        mongo.close()
        logger.info("%s exit", rcx.persona.persona_id)


def main():
    scenario_fn = ckit_bot_exec.parse_bot_args()
    fclient = ckit_client.FlexusClient(
        ckit_client.bot_service_name(BOT_NAME, BOT_VERSION),
        endpoint="/v1/jailed-bot",
    )

    asyncio.run(ckit_bot_exec.run_bots_in_this_group(
        fclient,
        marketable_name=BOT_NAME,
        marketable_version_str=BOT_VERSION,
        bot_main_loop=digital_twin_main_loop,
        inprocess_tools=TOOLS,
        scenario_fn=scenario_fn,
        install_func=digital_twin_install.install,
    ))


if __name__ == "__main__":
    main()
