import asyncio
import base64
import json
from pathlib import Path

from flexus_client_kit import ckit_client
from flexus_client_kit import ckit_bot_install
from digital_twin import digital_twin_prompts

BOT_DESCRIPTION = """
## Digital Twin - AI Representation of Art Koval

A sophisticated bot that creates an AI representation of a specific person by learning from uploaded documents.
The digital twin responds to messages in Art's voice, checks his calendar for context, and continuously learns
from corrections.

**Key Features:**

- **Progressive Training**: Upload documents (PDF, Word, Google Docs) to train the personality model
- **Multi-Channel Presence**: Responds to Telegram, Email, and Flexus chat messages
- **Calendar Integration**: Checks Google Calendar for availability and context
- **Notification System**: Notifies Art via Email + Telegram about every conversation
- **Learning Loop**: Detects "Actually I would say..." corrections and updates the model
- **Confidence Scoring**: Adds disclaimers when uncertain, transparent about AI nature
- **Action Capabilities**: Autonomous calendar actions, drafts other actions for approval

**Perfect for:**
- Delegating routine conversations while staying informed
- Maintaining presence across channels without constant availability
- Learning and adapting communication style over time
- Transparent AI representation with human oversight

The bot maintains Art's communication style, decision-making patterns, and expertise while allowing
him to review and correct responses for continuous improvement.
"""

DIGITAL_TWIN_SETUP_SCHEMA = [
    {
        "bs_name": "ART_EMAIL",
        "bs_type": "string_short",
        "bs_default": "",
        "bs_group": "Art's Contact Info",
        "bs_order": 1,
        "bs_importance": 2,
        "bs_description": "Art's email address for notifications about conversations",
    },
    {
        "bs_name": "ART_TELEGRAM_CHAT_ID",
        "bs_type": "string_short",
        "bs_default": "",
        "bs_group": "Art's Contact Info",
        "bs_order": 2,
        "bs_importance": 2,
        "bs_description": "Art's Telegram chat ID for notifications (get from @userinfobot)",
    },
    {
        "bs_name": "TELEGRAM_BOT_TOKEN",
        "bs_type": "string_long",
        "bs_default": "",
        "bs_group": "Telegram",
        "bs_order": 1,
        "bs_importance": 1,
        "bs_description": "Telegram Bot Token from @BotFather for the digital twin bot",
    },
    {
        "bs_name": "telegram_listen_mode",
        "bs_type": "string_short",
        "bs_default": "mentions",
        "bs_group": "Telegram",
        "bs_order": 2,
        "bs_importance": 0,
        "bs_description": "Listen to: all, mentions, dm (direct messages only)",
    },
    {
        "bs_name": "gmail_auto_respond",
        "bs_type": "bool",
        "bs_default": False,
        "bs_group": "Email",
        "bs_order": 1,
        "bs_importance": 0,
        "bs_description": "Automatically respond to incoming emails (requires OAuth setup)",
    },
    {
        "bs_name": "confidence_threshold",
        "bs_type": "int",
        "bs_default": 75,
        "bs_group": "Behavior",
        "bs_order": 1,
        "bs_importance": 0,
        "bs_description": "Minimum confidence (0-100) before adding disclaimer. Lower = more disclaimers.",
    },
    {
        "bs_name": "auto_calendar_actions",
        "bs_type": "bool",
        "bs_default": True,
        "bs_group": "Behavior",
        "bs_order": 2,
        "bs_importance": 0,
        "bs_description": "Allow bot to create calendar events autonomously (scheduling requests)",
    },
]

EXTRACTOR_LARK = """
result_text = ""
for msg in messages[::-1]:
    if msg.get("role") == "assistant":
        content = str(msg.get("content", ""))
        if "findings" in content or "section" in content:
            result_text = content
            break

if result_text:
    subchat_result = result_text
else:
    subchat_result = "No extraction completed"
"""

RESPONDER_LARK = """
result_text = ""
for msg in messages[::-1]:
    if msg.get("role") == "assistant":
        content = str(msg.get("content", ""))
        if "response" in content and "confidence" in content:
            result_text = content
            break

if result_text:
    subchat_result = result_text
else:
    subchat_result = "No response generated"
"""

LEARNER_LARK = """
result_text = ""
for msg in messages[::-1]:
    if msg.get("role") == "assistant":
        content = str(msg.get("content", ""))
        if "learning_type" in content or "principle" in content:
            result_text = content
            break

if result_text:
    subchat_result = result_text
else:
    subchat_result = "No learning extracted"
"""

DEFAULT_LARK = """
for msg in messages[::-1]:
    if msg.get("role") == "assistant":
        content = str(msg.get("content", ""))
        if "actually i would say" in content.lower():
            post_cd_instruction = "⚠️ Possible correction detected - use learn_from_correction() tool"
            break
"""


async def install(
    client: ckit_client.FlexusClient,
    ws_id: str,
    bot_name: str,
    bot_version: str,
    tools: list,
):
    bot_internal_tools = json.dumps([t.openai_style_tool() for t in tools])
    pic_big = base64.b64encode(open(Path(__file__).with_name("digital_twin-1024x1536.webp"), "rb").read()).decode("ascii")
    pic_small = base64.b64encode(open(Path(__file__).with_name("digital_twin-256x256.webp"), "rb").read()).decode("ascii")

    await ckit_bot_install.marketplace_upsert_dev_bot(
        client,
        ws_id=ws_id,
        marketable_name=bot_name,
        marketable_version=bot_version,
        marketable_accent_color="#7B68EE",
        marketable_title1="Digital Twin",
        marketable_title2="AI representation that learns your voice and responds like you would.",
        marketable_author="Flexus",
        marketable_occupation="Personal AI Representative",
        marketable_description=BOT_DESCRIPTION,
        marketable_typical_group="Productivity / AI Assistants",
        marketable_github_repo="https://github.com/smallcloudai/digital-twin-bot.git",
        marketable_run_this="python -m digital_twin.digital_twin_bot",
        marketable_setup_default=DIGITAL_TWIN_SETUP_SCHEMA,
        marketable_featured_actions=[
            {
                "feat_question": "Upload a document to train my personality model",
                "feat_expert": "default",
                "feat_depends_on_setup": [],
            },
            {
                "feat_question": "Show me my current personality model",
                "feat_expert": "default",
                "feat_depends_on_setup": [],
            },
            {
                "feat_question": "What conversations have you handled today?",
                "feat_expert": "default",
                "feat_depends_on_setup": ["TELEGRAM_BOT_TOKEN"],
            },
        ],
        marketable_intro_message="👋 Hi! I'm your Digital Twin bot. I learn from your documents to respond to messages in your voice. Upload some writing samples, emails, or memos to get started training my personality model.",
        marketable_preferred_model_default="grok-4-1-fast-reasoning",
        marketable_daily_budget_default=200_000,
        marketable_default_inbox_default=20_000,
        marketable_experts=[
            ("default", ckit_bot_install.FMarketplaceExpertInput(
                fexp_system_prompt=digital_twin_prompts.default_prompt,
                fexp_python_kernel=DEFAULT_LARK,
                fexp_block_tools="",
                fexp_allow_tools="",
                fexp_app_capture_tools=bot_internal_tools,
                fexp_description="Main conversational expert that handles incoming messages, generates responses in Art's voice, and manages notifications.",
            )),
            ("extractor", ckit_bot_install.FMarketplaceExpertInput(
                fexp_system_prompt=digital_twin_prompts.extractor_prompt,
                fexp_python_kernel=EXTRACTOR_LARK,
                fexp_block_tools="",
                fexp_allow_tools="",
                fexp_app_capture_tools=bot_internal_tools,
                fexp_description="Subchat expert for extracting personality traits, communication patterns, and knowledge from uploaded documents.",
            )),
            ("responder", ckit_bot_install.FMarketplaceExpertInput(
                fexp_system_prompt=digital_twin_prompts.responder_prompt,
                fexp_python_kernel=RESPONDER_LARK,
                fexp_block_tools="",
                fexp_allow_tools="",
                fexp_app_capture_tools=bot_internal_tools,
                fexp_description="Subchat expert for generating responses in Art's voice based on personality model and context.",
            )),
            ("learner", ckit_bot_install.FMarketplaceExpertInput(
                fexp_system_prompt=digital_twin_prompts.learner_prompt,
                fexp_python_kernel=LEARNER_LARK,
                fexp_block_tools="",
                fexp_allow_tools="",
                fexp_app_capture_tools=bot_internal_tools,
                fexp_description="Subchat expert for analyzing Art's corrections and extracting learnings to improve the personality model.",
            )),
        ],
        marketable_tags=["AI", "Productivity", "Communication", "Learning"],
        marketable_picture_big_b64=pic_big,
        marketable_picture_small_b64=pic_small,
        marketable_schedule=[],
        marketable_forms=ckit_bot_install.load_form_bundles(__file__),
    )


if __name__ == "__main__":
    from digital_twin import digital_twin_bot
    args = ckit_bot_install.bot_install_argparse()
    client = ckit_client.FlexusClient("digital_twin_install")
    asyncio.run(install(
        client,
        ws_id=args.ws,
        bot_name=digital_twin_bot.BOT_NAME,
        bot_version=digital_twin_bot.BOT_VERSION,
        tools=digital_twin_bot.TOOLS,
    ))
