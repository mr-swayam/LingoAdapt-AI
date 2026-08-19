import type { ConversationScenario } from "@/types/conversation";

export const SCENARIO_LABELS: Record<ConversationScenario, string> = {
  RESTAURANT: "Restaurant",
  AIRPORT: "Airport",
  JOB_INTERVIEW: "Job Interview",
  SHOPPING: "Shopping",
  CASUAL: "Casual Conversation",
  COLLEGE: "College",
  TRAVEL: "Travel",
};

export const SCENARIO_ICONS: Record<ConversationScenario, string> = {
  RESTAURANT: "🍽️",
  AIRPORT: "✈️",
  JOB_INTERVIEW: "💼",
  SHOPPING: "🛍️",
  CASUAL: "💬",
  COLLEGE: "🎓",
  TRAVEL: "🧳",
};
