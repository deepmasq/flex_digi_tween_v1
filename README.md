# Digital Twin Bot

## Overview

A Flexus bot that creates an AI representation of a specific person (Art Koval) by learning from uploaded documents. The digital twin responds to messages in Art's voice, checks his calendar for context, and continuously learns from corrections.

## Purpose

Art delegates conversations to his digital twin, which handles direct messages and mentions across Telegram, Email, and Flexus chat. The bot maintains Art's communication style, decision-making patterns, and expertise while allowing him to review and correct responses.

## Core Functionality

### 1. Progressive Training

- **Document Upload Interface**: Web UI where Art uploads personality/style documents
- **Supported Formats**: PDF, Word (.docx), Google Docs
- **Extraction Pipeline**:
  - Parse uploaded documents
  - Extract communication patterns (tone, vocabulary, sentence structure)
  - Identify decision-making frameworks and values
  - Build knowledge base of expertise domains
  - Detect behavioral patterns and preferences
- **Incremental Learning**: Model improves as more documents are added over time

### 2. Conversation Handling

**Trigger**: Direct mentions or DMs in Telegram, Email, or Flexus chat

**Response Flow**:
1. Receive incoming message
2. Check Google Calendar for Art's current context/availability
3. Analyze message intent and urgency
4. Generate response in Art's style using trained personality model
5. Add confidence disclaimer if uncertainty is high ("I'd confirm this with Art")
6. Send response to requester
7. Notify Art via Email + Telegram with conversation summary

**Channels**:
- Telegram (DMs and mentions)
- Email (direct emails)
- Flexus chat interface

### 3. Learning Loop

When Art receives a notification about a conversation:
- If Art replies "Actually I would say [X]", the bot captures this as a correction
- System extracts the delta between bot's response and Art's preferred response
- Updates personality model to incorporate the correction
- Similar future contexts will reflect the learned preference

### 4. Action Capabilities

**Calendar Actions** (autonomous):
- Check availability
- Suggest meeting times
- Block time slots
- Requires Google Calendar API access with write permissions

**Other Actions** (draft for approval):
- Sending emails on Art's behalf
- Making commitments or promises
- Financial decisions
- Strategic choices
- Bot drafts the action and asks Art to approve before executing

### 5. Google Calendar Integration

- OAuth connection to Art's Google Calendar
- Read access: Check availability, see event context
- Write access: Create/modify calendar events when responding to scheduling requests
- Context enrichment: "Art is in a board meeting right now" or "Art is available this afternoon"

## Personality Model

The bot maintains a structured representation based on the template:

1. **Identity Core**: Name, role, bio, current context
2. **Communication Style**: Tone, sentence patterns, vocabulary, verbal tics
3. **Knowledge Domains**: Areas of expertise, blind spots, influences
4. **Values & Decision-Making**: Priorities, frameworks, risk tolerance, strong opinions
5. **Relationships**: Key people and relationship dynamics
6. **Behavioral Rules**: How to handle uncertainty, conflicts, different audiences

## Technical Architecture

### Components

1. **Document Processor**
   - File upload handler
   - Text extraction (PDF, DOCX, Google Docs)
   - NLP pipeline for personality extraction
   - Embeddings storage for retrieval

2. **Personality Engine**
   - Structured personality model storage
   - Style mimicry layer (tone, vocabulary, patterns)
   - Decision-making simulator
   - Confidence scoring

3. **Conversation Manager**
   - Multi-channel listener (Telegram, Email, Flexus)
   - Message intent classifier
   - Response generator
   - Context injector (calendar data)

4. **Learning Module**
   - Correction detector ("Actually I would say...")
   - Delta extraction
   - Model update pipeline
   - Feedback loop tracker

5. **Integration Layer**
   - Google Calendar API client
   - Telegram Bot API
   - Email SMTP/IMAP handlers
   - Notification dispatcher

### Data Storage

- **Uploaded Documents**: Raw files stored securely, metadata indexed
- **Personality Model**: Structured JSON representation with versioning
- **Conversation History**: All interactions logged with timestamps
- **Corrections**: Tracked separately for analysis and model updates
- **Calendar Cache**: Recent calendar data for faster responses

## User Experience

### For Art (the represented person):

1. **Onboarding**:
   - Access web interface
   - Upload initial documents (emails, writing samples, memos)
   - Connect Google Calendar (OAuth flow)
   - Configure notification preferences (Email + Telegram)
   - Test the bot with sample questions

2. **Ongoing Usage**:
   - Receive notifications when digital twin has conversations
   - Review responses and provide corrections as needed
   - Upload new documents periodically to improve accuracy
   - Monitor dashboard showing conversation volume and topics

3. **Correction Flow**:
   - Notification: "Your twin responded to Jane about Q4 strategy"
   - If response needs correction, reply: "Actually I would say we should prioritize retention over acquisition"
   - Bot learns and thanks Art for the feedback

### For People Talking to the Twin:

1. Send a message to Art via Telegram, Email, or Flexus
2. Receive response in Art's voice, usually within seconds
3. If bot is uncertain, response includes disclaimer: "I'd confirm this with Art directly"
4. Transparent about being a digital twin if asked directly

## Privacy & Security

- **Access Control**: Public (anyone can talk to the twin)
- **Data Isolation**: Art's documents and model stay in his Flexus workspace
- **Calendar Privacy**: Only availability and basic context shared, not full event details
- **Audit Trail**: All conversations logged and accessible to Art
- **Correction Privacy**: Art's corrections stored securely, not visible to original requester

## Success Metrics

- **Accuracy**: % of responses Art doesn't need to correct
- **Response Time**: Average time from message to twin response
- **Coverage**: % of conversations twin handles vs. escalated to Art
- **Learning Rate**: Improvement in accuracy over time as documents are added
- **User Satisfaction**: Feedback from people interacting with the twin

## Limitations & Transparency

- Bot always discloses it's a digital twin if asked directly
- Cannot make high-stakes decisions without Art's approval
- Adds disclaimers when confidence is below threshold
- Real Art can override or correct any response
- Not a replacement for Art in sensitive or complex situations

## Future Enhancements

- Voice/video call handling (transcribe → respond → synthesize in Art's voice)
- Multi-person twins (let others create their own digital twins)
- Context-specific personalities (work vs. personal mode)
- Proactive reach-out ("Art wanted me to follow up with you about...")
- Meeting attendance (twin attends meetings on Art's behalf, takes notes)
- Integration with CRM, project management tools for deeper context

## Example Interactions

### Example 1: Scheduling Request

**Requester**: "Hey Art, can we meet next Tuesday to discuss the Q2 roadmap?"

**Digital Twin**:
- Checks Google Calendar
- Sees Art has a 2-hour block free Tuesday afternoon
- Responds: "Tuesday works! I have 2-4pm open. Want to grab that slot? I'll send a calendar invite."
- Notifies Art: "Scheduled tentative meeting with [Name] for Tue 2pm re: Q2 roadmap. Approve?"
- If Art approves, creates calendar event

### Example 2: Technical Question

**Requester**: "What's your take on using microservices vs. monolith for our new platform?"

**Digital Twin**:
- Checks personality model for Art's known positions on architecture
- Finds strong opinions on starting with monolith
- Responds: "Start with a monolith. Microservices sound great but they're overkill until you hit real scale problems. You'll spend more time on infrastructure than features. Break it apart later when you actually need to. That said, I'd confirm this with Art directly if it's a big decision - architecture choices are hard to reverse."
- Notifies Art with full context

### Example 3: Correction Loop

**Requester**: "Should we hire a senior engineer or two mid-level engineers?"

**Digital Twin**: "Go with the senior engineer. One great engineer is worth three good ones."

**Art's Correction**: "Actually I would say it depends on the team dynamics right now. If we have good senior coverage already, two mid-levels give us more velocity. If we're lacking technical leadership, then senior for sure."

**Bot Learning**: Updates model to include "hiring decisions depend on current team composition" and "avoid absolute statements about hiring"

## Implementation Priorities

**Phase 1 (MVP)**:
- Document upload and basic extraction
- Simple personality model (tone, style)
- Telegram integration
- Basic notifications to Art
- Manual correction capture

**Phase 2**:
- Google Calendar integration
- Email integration
- Automated learning from corrections
- Confidence scoring and disclaimers

**Phase 3**:
- Advanced personality extraction (values, decision frameworks)
- Action capabilities (calendar writes, draft approvals)
- Dashboard and analytics
- Flexus chat interface

---

**Bot Name**: `digital_twin`
**Primary Owner**: Art Koval
**Status**: Specification phase