"use client";

import { useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { api } from "../lib/api";
import {
  AgentRun,
  Approval,
  AuthUser,
  Attempt,
  Dataset,
  DryRecord,
  DryRun,
  HistoryEvent,
  MigrationRun,
  Plan,
  Profile,
  Project,
  Question,
  RootState,
  SchemaSnapshot,
  resetMigration,
  resetWorkflow,
  updateWorkflow,
} from "../lib/store";

type Proposal = {
  explanation?: string;
  mappings?: unknown[];
  risks?: unknown[];
  missing_source_fields?: string[];
  incompatible_fields?: string[];
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
};

const panel = "rounded-2xl border border-line bg-panel p-5 shadow-sm";
const input = "w-full rounded-lg border border-line bg-white px-3 py-2.5 text-sm outline-none focus:border-brand";
const primary = "rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-dark disabled:hover:bg-brand";
const secondary = "rounded-lg border border-line bg-white px-4 py-2.5 text-sm font-semibold hover:bg-stone-50";

function JsonView({ value }: { value: unknown }) {
  return <pre className="mt-3 max-h-80 overflow-auto rounded-xl bg-ink p-4 text-xs text-emerald-100">{JSON.stringify(value, null, 2)}</pre>;
}

function FileField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const [name, setName] = useState("");
  return (
    <label className="block rounded-xl border border-dashed border-line bg-white p-4">
      <span className="block text-sm font-semibold">{label}</span>
      <span className="mt-1 block text-xs text-muted">JSON file only</span>
      <input
        className="mt-3 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-emerald-50 file:px-3 file:py-2 file:font-semibold file:text-brand"
        type="file"
        accept=".json,application/json"
        onChange={async (event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          onChange(await file.text());
          setName(file.name);
        }}
      />
      {value && <span className="mt-2 block text-xs font-medium text-brand">Loaded: {name}</span>}
    </label>
  );
}

export default function Home() {
  const dispatch = useDispatch();
  const flow = useSelector((state: RootState) => state.workflow);
  const [projectName, setProjectName] = useState("");
  const [namespace, setNamespace] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [targetText, setTargetText] = useState("");
  const [datasetText, setDatasetText] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [comment, setComment] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Upload the three JSON files to begin.");

  const proposal = flow.agent?.proposal as Proposal | null;
  const accepted = useMemo(() => flow.records.filter((item) => item.status === "accepted"), [flow.records]);
  const rejected = useMemo(() => flow.records.filter((item) => item.status === "rejected"), [flow.records]);

  function fail(error: unknown, fallback: string) {
    setMessage(error instanceof Error ? error.message : fallback);
  }

  async function authenticate() {
    setBusy(true);
    setMessage(authMode === "login" ? "Signing in…" : "Creating your account…");
    try {
      const result = await api<AuthResponse>(`/auth/${authMode}`, null, {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          password,
          ...(authMode === "register" ? { display_name: displayName.trim() } : {}),
        }),
      });
      dispatch(updateWorkflow({ accessToken: result.access_token, user: result.user }));
      setPassword("");
      setMessage("Signed in. Upload the three JSON files to begin.");
    } catch (error) {
      fail(error, "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  async function loadQuestions(projectId: string, agentId: string) {
    return api<Question[]>(`/projects/${projectId}/agent-runs/${agentId}/questions`, flow.accessToken);
  }

  async function loadHistory(projectId: string) {
    return api<HistoryEvent[]>(`/projects/${projectId}/history`, flow.accessToken);
  }

  async function loadAllRecords(projectId: string, planId: string, dryRunId: string) {
    const base = `/projects/${projectId}/plans/${planId}/dry-runs/${dryRunId}/records`;
    const first = await api<{ items: DryRecord[]; pagination: { total_pages: number } }>(`${base}?page=1&page_size=200`, flow.accessToken);
    const records = [...first.items];
    for (let page = 2; page <= first.pagination.total_pages; page += 1) {
      const next = await api<{ items: DryRecord[] }>(`${base}?page=${page}&page_size=200`, flow.accessToken);
      records.push(...next.items);
    }
    return records;
  }

  async function createInputs() {
    setBusy(true);
    setMessage("Validating files and creating the project…");
    try {
      let project = flow.project;
      let sourceSchema = flow.sourceSchema;
      let targetSchema = flow.targetSchema;
      let dataset = flow.dataset;
      let profile = flow.profile;

      if (!project) {
        if (!projectName.trim() || !namespace.trim()) throw new Error("Project name and target namespace are required.");
        project = await api<Project>("/projects", flow.accessToken, {
          method: "POST",
          body: JSON.stringify({ name: projectName.trim(), description: null, target_namespace: namespace.trim() }),
        });
        dispatch(updateWorkflow({ project }));
      }
      if (!sourceSchema) {
        if (!sourceText) throw new Error("Select the source schema JSON file.");
        sourceSchema = await api<SchemaSnapshot>(`/projects/${project.id}/schemas`, flow.accessToken, {
          method: "POST",
          body: JSON.stringify(JSON.parse(sourceText)),
        });
        dispatch(updateWorkflow({ sourceSchema }));
      }
      if (!targetSchema) {
        if (!targetText) throw new Error("Select the target schema JSON file.");
        targetSchema = await api<SchemaSnapshot>(`/projects/${project.id}/schemas`, flow.accessToken, {
          method: "POST",
          body: JSON.stringify(JSON.parse(targetText)),
        });
        dispatch(updateWorkflow({ targetSchema }));
      }
      if (!dataset) {
        if (!datasetText) throw new Error("Select the source records JSON file.");
        const records = JSON.parse(datasetText);
        if (!Array.isArray(records) || records.length === 0) throw new Error("The source records file must contain a non-empty JSON array.");
        dataset = await api<Dataset>(
          `/projects/${project.id}/datasets?source_schema_snapshot_id=${sourceSchema.id}`,
          flow.accessToken,
          { method: "POST", body: JSON.stringify(records) },
        );
        dispatch(updateWorkflow({ dataset }));
      }
      if (!profile) {
        profile = await api<Profile>(`/projects/${project.id}/datasets/${dataset.id}/profile`, flow.accessToken, { method: "POST" });
        dispatch(updateWorkflow({ profile }));
      }

      dispatch(updateWorkflow({ step: 2, project, sourceSchema, targetSchema, dataset, profile }));
      setMessage("Inputs stored and profiled. Start the AI mapping agent.");
    } catch (error) {
      fail(error, "Unable to create the migration inputs.");
    } finally {
      setBusy(false);
    }
  }

  async function startAgent() {
    if (!flow.project || !flow.sourceSchema || !flow.targetSchema || !flow.dataset) return;
    setBusy(true);
    setMessage("Qwen is inspecting the schemas, profile, sample, and supported rules…");
    try {
      const agent = await api<AgentRun>(`/projects/${flow.project.id}/agent-runs`, flow.accessToken, {
        method: "POST",
        body: JSON.stringify({
          dataset_id: flow.dataset.id,
          source_schema_id: flow.sourceSchema.id,
          target_schema_id: flow.targetSchema.id,
        }),
      });
      const questions = await loadQuestions(flow.project.id, agent.id);
      dispatch(updateWorkflow({ agent, questions, plan: null, dryRun: null, records: [], approval: null, migrationRun: null }));
      setMessage(agent.status === "needs_clarification" ? "The agent needs your clarification before continuing." : "The proposed plan is ready for a deterministic dry run.");
    } catch (error) {
      fail(error, "The mapping agent could not start.");
    } finally {
      setBusy(false);
    }
  }

  async function answerQuestion(questionId: string) {
    if (!flow.project || !flow.agent) return;
    const answer = answers[questionId]?.trim();
    if (!answer) return;
    setBusy(true);
    try {
      await api(`/projects/${flow.project.id}/agent-runs/${flow.agent.id}/questions/${questionId}/answer`, flow.accessToken, {
        method: "POST",
        body: JSON.stringify({ answer }),
      });
      const questions = await loadQuestions(flow.project.id, flow.agent.id);
      dispatch(updateWorkflow({ questions }));
      setMessage("Answer saved in PostgreSQL.");
    } catch (error) {
      fail(error, "Unable to save the answer.");
    } finally {
      setBusy(false);
    }
  }

  async function resumeAgent() {
    if (!flow.project || !flow.agent) return;
    setBusy(true);
    setMessage("Resuming the same LangGraph checkpoint…");
    try {
      const agent = await api<AgentRun>(`/projects/${flow.project.id}/agent-runs/${flow.agent.id}/resume`, flow.accessToken, { method: "POST" });
      const questions = await loadQuestions(flow.project.id, agent.id);
      dispatch(updateWorkflow({ agent, questions }));
      setMessage(agent.status === "ready_for_review" ? "Revised plan ready. Create the full dry run." : `Agent status: ${agent.status}`);
    } catch (error) {
      fail(error, "Unable to resume the agent.");
    } finally {
      setBusy(false);
    }
  }

  async function createDryRun() {
    if (!flow.project || !flow.agent?.plan_id) return;
    setBusy(true);
    setMessage("Running every source record with deterministic rules…");
    try {
      const plan = await api<Plan>(`/projects/${flow.project.id}/plans/${flow.agent.plan_id}`, flow.accessToken);
      const dryRun = await api<DryRun>(`/projects/${flow.project.id}/plans/${plan.id}/dry-runs`, flow.accessToken, { method: "POST" });
      const records = await loadAllRecords(flow.project.id, plan.id, dryRun.id);
      const history = await loadHistory(flow.project.id);
      dispatch(updateWorkflow({ step: 3, plan, dryRun, records, history }));
      setMessage("Dry run complete. Review all mappings, counts, and errors before deciding.");
    } catch (error) {
      fail(error, "The dry run failed.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "approved" | "rejected") {
    if (!flow.project || !flow.plan || !flow.dryRun) return;
    setBusy(true);
    try {
      const approval = await api<Approval>(
        `/projects/${flow.project.id}/plans/${flow.plan.id}/dry-runs/${flow.dryRun.id}/approval`,
        flow.accessToken,
        { method: "POST", body: JSON.stringify({ decision, comment: comment.trim() || null }) },
      );
      const history = await loadHistory(flow.project.id);
      dispatch(updateWorkflow({ approval, history }));
      setMessage(decision === "approved" ? "Exact dry run approved. It is now eligible for execution." : "Proposal rejected. Start a new agent proposal to make changes.");
    } catch (error) {
      fail(error, "Unable to save the decision.");
    } finally {
      setBusy(false);
    }
  }

  async function execute() {
    if (!flow.project || !flow.approval) return;
    setBusy(true);
    try {
      const executionKey = flow.executionKey ?? crypto.randomUUID();
      const migrationRun = await api<MigrationRun>(
        `/projects/${flow.project.id}/approvals/${flow.approval.id}/execute`,
        flow.accessToken,
        { method: "POST", headers: { "Idempotency-Key": executionKey } },
      );
      const [attempts, history] = await Promise.all([
        api<Attempt[]>(`/projects/${flow.project.id}/migration-runs/${migrationRun.id}/attempts`, flow.accessToken),
        loadHistory(flow.project.id),
      ]);
      dispatch(updateWorkflow({ step: 4, executionKey, migrationRun, attempts, history }));
      setMessage("Accepted records inserted. Repeating execution uses the same safe retry key.");
    } catch (error) {
      fail(error, "Migration execution failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action: "reconcile" | "rollback") {
    if (!flow.project || !flow.migrationRun) return;
    setBusy(true);
    try {
      const path = `/projects/${flow.project.id}/migration-runs/${flow.migrationRun.id}/${action}`;
      let migrationRun = flow.migrationRun;
      if (action === "reconcile") {
        const result = await api<{ migration_status: string; details: Record<string, unknown> }>(path, flow.accessToken, { method: "POST" });
        migrationRun = { ...migrationRun, status: result.migration_status, reconciliation: result.details };
      } else {
        migrationRun = await api<MigrationRun>(path, flow.accessToken, { method: "POST" });
      }
      const [attempts, history] = await Promise.all([
        api<Attempt[]>(`/projects/${flow.project.id}/migration-runs/${migrationRun.id}/attempts`, flow.accessToken),
        loadHistory(flow.project.id),
      ]);
      dispatch(updateWorkflow({ migrationRun, attempts, history }));
      setMessage(action === "reconcile" ? "Source, ledger, and target evidence compared." : migrationRun.status === "rollback_conflict" ? "Rollback blocked because target data changed." : "Owned target rows rolled back safely.");
    } catch (error) {
      fail(error, `Unable to ${action} the migration.`);
    } finally {
      setBusy(false);
    }
  }

  function newMigration() {
    dispatch(resetMigration());
    setProjectName("");
    setNamespace("");
    setSourceText("");
    setTargetText("");
    setDatasetText("");
    setAnswers({});
    setComment("");
    setMessage("Upload the three JSON files to begin.");
  }

  function logout() {
    dispatch(resetWorkflow());
    setMessage("Signed out.");
  }

  if (!flow.accessToken || !flow.user) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-md items-center px-4 py-10">
        <section className={`${panel} w-full`}>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand">Controlled data migration</p>
          <h1 className="mt-2 text-3xl font-bold">SchemaBridge</h1>
          <p className="mt-2 text-sm text-muted">Sign in to create and manage your migration projects.</p>
          <div className="mt-5 grid grid-cols-2 rounded-lg bg-stone-100 p-1">
            <button className={`rounded-md px-3 py-2 text-sm font-semibold ${authMode === "login" ? "bg-white shadow-sm" : "text-muted"}`} onClick={() => setAuthMode("login")}>Login</button>
            <button className={`rounded-md px-3 py-2 text-sm font-semibold ${authMode === "register" ? "bg-white shadow-sm" : "text-muted"}`} onClick={() => setAuthMode("register")}>Create account</button>
          </div>
          <div className="mt-5 space-y-4">
            {authMode === "register" && <label className="block text-sm font-semibold">Name<input className={`${input} mt-2`} value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" /></label>}
            <label className="block text-sm font-semibold">Email<input className={`${input} mt-2`} type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" /></label>
            <label className="block text-sm font-semibold">Password<input className={`${input} mt-2`} type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={authMode === "login" ? "current-password" : "new-password"} /></label>
          </div>
          <button className={`${primary} mt-5 w-full`} disabled={busy || !email.trim() || password.length < (authMode === "register" ? 8 : 1) || (authMode === "register" && !displayName.trim())} onClick={authenticate}>{busy ? "Please wait…" : authMode === "login" ? "Login" : "Create account"}</button>
          <p className="mt-4 text-sm font-medium text-red-700">{message === "Upload the three JSON files to begin." ? "" : message}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-4 py-8 sm:px-6">
      <header className="mb-6 flex flex-col justify-between gap-4 border-b border-line pb-6 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand">Controlled data migration</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">SchemaBridge</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">Upload schemas and JSON records. The agent proposes a mapping; deterministic code validates, transforms, and preserves evidence.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2"><span className="text-sm text-muted">{flow.user.display_name}</span><button className={secondary} onClick={newMigration}>New migration</button><button className={secondary} onClick={logout}>Logout</button></div>
      </header>

      <nav className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {["Upload inputs", "AI mapping", "Review dry run", "Migration result"].map((label, index) => {
          const number = index + 1;
          return <div key={label} className={`rounded-xl border px-3 py-3 text-sm font-semibold ${flow.step === number ? "border-brand bg-emerald-50 text-brand" : flow.step > number ? "border-emerald-200 bg-white text-emerald-700" : "border-line bg-white text-muted"}`}>{number}. {label}</div>;
        })}
      </nav>

      <div className="mb-5 rounded-xl border border-line bg-white px-4 py-3 text-sm font-medium">
        {busy ? "Working… " : ""}{message}
      </div>

      {flow.step === 1 && (
        <section className={panel}>
          <h2 className="text-xl font-bold">1. Upload migration inputs</h2>
          <p className="mt-1 text-sm text-muted">The application generates and connects all IDs automatically.</p>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-semibold">Project name<input className={`${input} mt-2`} value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Customer migration" /></label>
            <label className="text-sm font-semibold">Target namespace<input className={`${input} mt-2`} value={namespace} onChange={(event) => setNamespace(event.target.value)} placeholder="mock_customers" /></label>
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <FileField label="Source schema" value={sourceText} onChange={setSourceText} />
            <FileField label="Target schema" value={targetText} onChange={setTargetText} />
            <FileField label="Source records" value={datasetText} onChange={setDatasetText} />
          </div>
          <button className={`${primary} mt-5`} disabled={busy || (!flow.sourceSchema && !sourceText) || (!flow.targetSchema && !targetText) || (!flow.dataset && !datasetText)} onClick={createInputs}>Create project and profile data</button>
        </section>
      )}

      {flow.step === 2 && flow.project && (
        <section className="space-y-5">
          <div className={panel}>
            <h2 className="text-xl font-bold">2. Generate the mapping plan</h2>
            <p className="mt-1 text-sm text-muted">Project <strong>{flow.project.name}</strong> contains {flow.dataset?.record_count} source records. Qwen can inspect only these saved inputs and the supported rule list.</p>
            {!flow.agent && <button className={`${primary} mt-5`} disabled={busy} onClick={startAgent}>Start AI mapping</button>}
            {flow.agent && <div className="mt-4 flex flex-wrap items-center gap-3"><span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold text-brand">{flow.agent.status}</span><button className={secondary} disabled={busy} onClick={startAgent}>Generate a new proposal</button></div>}
          </div>

          {flow.agent && proposal && (
            <div className="grid gap-5 lg:grid-cols-2">
              <article className={panel}><h3 className="font-bold">Agent explanation</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted">{proposal.explanation}</p></article>
              <article className={panel}><h3 className="font-bold">Mappings and risks</h3><JsonView value={{ mappings: proposal.mappings, risks: proposal.risks, missing_source_fields: proposal.missing_source_fields, incompatible_fields: proposal.incompatible_fields }} /></article>
            </div>
          )}

          {flow.questions.some((question) => !question.answer) && (
            <div className={panel}>
              <h3 className="font-bold">Clarification required</h3>
              {flow.questions.map((question) => <div className="mt-4 border-t border-line pt-4" key={question.id}><p className="font-semibold">{question.question}</p><p className="mt-1 text-sm text-muted">{question.reason}</p>{question.answer ? <p className="mt-2 text-sm font-semibold text-brand">Answered: {question.answer}</p> : <div className="mt-3 flex flex-col gap-2 sm:flex-row"><input className={input} value={answers[question.id] ?? ""} onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })} placeholder="Your decision" /><button className={primary} disabled={busy || !answers[question.id]?.trim()} onClick={() => answerQuestion(question.id)}>Save answer</button></div>}</div>)}
              <button className={`${primary} mt-5`} disabled={busy || flow.questions.some((question) => !question.answer)} onClick={resumeAgent}>Resume saved agent run</button>
            </div>
          )}

          {flow.agent?.status === "needs_clarification" && flow.questions.length > 0 && flow.questions.every((question) => question.answer) && <button className={primary} disabled={busy} onClick={resumeAgent}>Resume saved agent run</button>}
          {flow.agent?.status === "ready_for_review" && flow.agent.plan_id && <button className={primary} disabled={busy} onClick={createDryRun}>Run all source records</button>}
          {flow.agent && ["failed", "invalid"].includes(flow.agent.status) && <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">The proposal could not become a valid plan. Generate a new proposal after checking the schemas and answers.</p>}
        </section>
      )}

      {flow.step === 3 && flow.dryRun && flow.plan && (
        <section className="space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[['Source', flow.dryRun.source_count], ['Transformed', flow.dryRun.transformed_count], ['Accepted', flow.dryRun.accepted_count], ['Rejected', flow.dryRun.rejected_count]].map(([label, count]) => <article className={`${panel} !p-4`} key={String(label)}><span className="text-xs font-semibold text-muted">{label}</span><strong className="mt-1 block text-3xl">{count}</strong></article>)}
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <article className={panel}><h3 className="font-bold">Plan version {flow.plan.version}: {flow.plan.name}</h3><JsonView value={flow.plan.plan_data} /></article>
            <article className={panel}><h3 className="font-bold">AI risks and explanation</h3><JsonView value={{ risks: proposal?.risks, explanation: proposal?.explanation }} /></article>
          </div>
          <article className={panel}><h3 className="font-bold text-emerald-800">Accepted records ({accepted.length})</h3><div className="mt-3 grid gap-3 md:grid-cols-2">{accepted.map((record) => <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3" key={record.id}><span className="text-xs font-semibold">Row {record.row_ordinal}</span><JsonView value={record.transformed_record} /></div>)}</div></article>
          <article className={`${panel} border-red-200 bg-red-50`}><h3 className="font-bold text-red-800">Rejected records ({rejected.length})</h3>{rejected.length === 0 ? <p className="mt-2 text-sm text-muted">No rejected records.</p> : <div className="mt-3 grid gap-3 md:grid-cols-2">{rejected.map((record) => <div className="rounded-xl border border-red-200 bg-white p-3" key={record.id}><span className="text-xs font-semibold">Row {record.row_ordinal}</span><JsonView value={{ transformed: record.transformed_record, errors: record.field_errors }} /></div>)}</div>}</article>
          <article className={panel}>
            <h3 className="font-bold">Approve this exact result</h3>
            <p className="mt-1 text-sm text-muted">Approval is tied to the schemas, dataset, plan, rules, dry-run hash, and target revision.</p>
            <textarea className={`${input} mt-4 min-h-24`} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Optional review comment" />
            {!flow.approval && <div className="mt-4 flex gap-3"><button className={primary} disabled={busy} onClick={() => decide("approved")}>Approve exact dry run</button><button className={secondary} disabled={busy} onClick={() => decide("rejected")}>Reject</button></div>}
            {flow.approval && <p className="mt-4 text-sm font-semibold">Decision: <span className={flow.approval.decision === "approved" ? "text-brand" : "text-red-700"}>{flow.approval.decision}</span></p>}
            {flow.approval?.decision === "approved" && <button className={`${primary} mt-4`} disabled={busy} onClick={execute}>Execute accepted records</button>}
            {flow.approval?.decision === "rejected" && <button className={`${primary} mt-4`} disabled={busy} onClick={() => { dispatch(updateWorkflow({ step: 2, agent: null, questions: [], plan: null, dryRun: null, records: [], approval: null })); setMessage("Start a new proposal. The rejected decision remains in history."); }}>Create a revised proposal</button>}
          </article>
        </section>
      )}

      {flow.step === 4 && flow.migrationRun && (
        <section className="space-y-5">
          <article className={panel}>
            <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">4. Migration result</h2><p className="mt-1 text-sm text-muted">Status: <strong>{flow.migrationRun.status}</strong> · Inserted: <strong>{flow.migrationRun.inserted_count}</strong></p></div><div className="flex flex-wrap gap-2"><button className={secondary} disabled={busy} onClick={execute}>Retry safely</button><button className={primary} disabled={busy} onClick={() => runAction("reconcile")}>Reconcile</button><button className="rounded-lg bg-red-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-800 disabled:hover:bg-red-700" disabled={busy || flow.migrationRun.status === "rolled_back"} onClick={() => runAction("rollback")}>Roll back</button></div></div>
            <JsonView value={flow.migrationRun.reconciliation} />
          </article>
          <div className="grid gap-5 lg:grid-cols-2">
            <article className={panel}><h3 className="font-bold">Attempts</h3>{flow.attempts.map((item) => <div className="border-t border-line py-3 text-sm" key={item.id}><strong>{item.action}</strong><span className="ml-2 text-muted">{item.status} · {new Date(item.created_at).toLocaleString()}</span></div>)}</article>
            <article className={panel}><h3 className="font-bold">Project history</h3>{flow.history.map((item) => <div className="border-t border-line py-3 text-sm" key={item.id}><strong>{item.event_type}</strong><span className="ml-2 text-muted">{item.actor_id} · {new Date(item.created_at).toLocaleString()}</span></div>)}</article>
          </div>
        </section>
      )}

      {flow.project && <details className="mt-6 rounded-xl border border-line bg-white p-4 text-xs text-muted"><summary className="cursor-pointer font-semibold">Generated references</summary><JsonView value={{ project_id: flow.project.id, source_schema_id: flow.sourceSchema?.id, target_schema_id: flow.targetSchema?.id, dataset_id: flow.dataset?.id, agent_run_id: flow.agent?.id, plan_id: flow.plan?.id ?? flow.agent?.plan_id, dry_run_id: flow.dryRun?.id, approval_id: flow.approval?.id, migration_run_id: flow.migrationRun?.id }} /></details>}
    </main>
  );
}
