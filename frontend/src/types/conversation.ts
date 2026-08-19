export const CONVERSATION_SCENARIOS = [
  "RESTAURANT",
  "AIRPORT",
  "JOB_INTERVIEW",
  "SHOPPING",
  "CASUAL",
  "COLLEGE",
  "TRAVEL",
] as const;

export type ConversationScenario = (typeof CONVERSATION_SCENARIOS)[number];

export type ConversationStatus = "ACTIVE" | "ENDED";

export type MessageRole = "LEARNER" | "TUTOR";

export type ConversationSkill =
  | "PAST_TENSE"
  | "PREPOSITIONS"
  | "ARTICLES"
  | "SUBJECT_VERB_AGREEMENT"
  | "PLURALS"
  | "WORD_CHOICE"
  | "GENERAL";

export type ConversationMessage = {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
};

export type Conversation = {
  id: string;
  scenario: ConversationScenario;
  status: ConversationStatus;
  summary: string | null;
  started_at: string;
  ended_at: string | null;
};

export type ConversationDetail = Conversation & {
  messages: ConversationMessage[];
};

export type Correction = {
  original: string;
  corrected: string;
  explanation: string;
  skill: ConversationSkill;
};

export type SendMessageResponse = {
  learner_message: ConversationMessage;
  tutor_message: ConversationMessage;
  corrections: Correction[];
};

export type VoiceSendMessageResponse = SendMessageResponse & { transcript: string };
