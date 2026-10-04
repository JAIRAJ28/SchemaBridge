import { configureStore, createSlice, PayloadAction } from "@reduxjs/toolkit";

export type JsonObject = Record<string, unknown>;
export type AuthUser = { id: string; email: string; display_name: string; is_active: boolean };

export type Project = JsonObject & { id: string; name: string };
export type SchemaSnapshot = JsonObject & { id: string; schema_role: string };
export type Dataset = JsonObject & { id: string; record_count: number };
export type Profile = JsonObject & { status: string };
export type AgentRun = JsonObject & {
  id: string;
  status: string;
  plan_id: string | null;
  proposal: JsonObject | null;
};
export type Question = JsonObject & {
  id: string;
  question: string;
  reason: string;
  answer: string | null;
};
export type Plan = JsonObject & {
  id: string;
  version: number;
  name: string;
  plan_data: JsonObject;
};
export type DryRun = JsonObject & {
  id: string;
  source_count: number;
  transformed_count: number;
  accepted_count: number;
  rejected_count: number;
  result_hash: string;
  target_revision: number;
};
export type DryRecord = JsonObject & {
  id: string;
  row_ordinal: number;
  status: "accepted" | "rejected";
  transformed_record: JsonObject;
  field_errors: JsonObject[];
};
export type Approval = JsonObject & {
  id: string;
  decision: "approved" | "rejected";
  bundle_fingerprint: string;
};
export type MigrationRun = JsonObject & {
  id: string;
  status: string;
  inserted_count: number;
  reconciliation: JsonObject;
};
export type Attempt = JsonObject & {
  id: string;
  action: string;
  status: string;
  created_at: string;
};
export type HistoryEvent = JsonObject & {
  id: string;
  event_type: string;
  actor_id: string;
  created_at: string;
};

export type WorkflowState = {
  step: number;
  accessToken: string | null;
  user: AuthUser | null;
  project: Project | null;
  sourceSchema: SchemaSnapshot | null;
  targetSchema: SchemaSnapshot | null;
  dataset: Dataset | null;
  profile: Profile | null;
  agent: AgentRun | null;
  questions: Question[];
  plan: Plan | null;
  dryRun: DryRun | null;
  records: DryRecord[];
  approval: Approval | null;
  migrationRun: MigrationRun | null;
  attempts: Attempt[];
  history: HistoryEvent[];
  executionKey: string | null;
};

const initialState: WorkflowState = {
  step: 1,
  accessToken: null,
  user: null,
  project: null,
  sourceSchema: null,
  targetSchema: null,
  dataset: null,
  profile: null,
  agent: null,
  questions: [],
  plan: null,
  dryRun: null,
  records: [],
  approval: null,
  migrationRun: null,
  attempts: [],
  history: [],
  executionKey: null,
};

const workflowSlice = createSlice({
  name: "workflow",
  initialState,
  reducers: {
    updateWorkflow: (state, action: PayloadAction<Partial<WorkflowState>>) => ({
      ...state,
      ...action.payload,
    }),
    restoreWorkflow: (_state, action: PayloadAction<WorkflowState>) => action.payload,
    resetWorkflow: () => initialState,
    resetMigration: (state) => ({
      ...initialState,
      accessToken: state.accessToken,
      user: state.user,
    }),
  },
});

export const { updateWorkflow, restoreWorkflow, resetWorkflow, resetMigration } = workflowSlice.actions;

export const store = configureStore({
  reducer: { workflow: workflowSlice.reducer },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
