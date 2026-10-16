/*
 * VP Studio — Simple mode editor (author) + stubs for Advanced mode and the
 * Player. Vue 3 from a CDN, runtime-compiled templates, no build step.
 * Case rules live in casemodel.js; this file is UI and server calls.
 * Templates use [[ ]] delimiters: {{ }} belongs to prompt fields.
 */
import {
  createApp, reactive, computed, ref, watch, nextTick, onMounted, onBeforeUnmount,
} from 'https://cdn.jsdelivr.net/npm/vue@3.5.13/dist/vue.esm-browser.prod.js';
import { initAuth, apiFetch, signOut, AuthError } from '/static/common/auth.js';
import * as M from './casemodel.js';

// ── store ────────────────────────────────────────────────────────────────────

const LS_PREVIEW_WIDTH = 'vp.previewWidth';
const LS_LAST_CASE = 'vp.lastCase';

function lsGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
function lsSet(key, value) { try { localStorage.setItem(key, value); } catch { /* private mode */ } }

const store = reactive({
  booting: true,
  user: null,
  authError: '',
  pack: null,
  levels: {},
  systemFields: [],
  cases: [],
  current: null,          // {id, revision, status}
  doc: null,
  saved: '',              // JSON of the last saved document
  saving: false,
  mode: 'author',         // 'author' | 'player'
  view: 'gallery',        // 'gallery' | 'editor'
  ui: {
    openStep: null, settingsOpen: false, legendOpen: false, tplOpen: false,
    previewOpen: false, previewWidth: Number(lsGet(LS_PREVIEW_WIDTH)) || 400, stratOpen: false, stratSel: null,
    stepMenu: null, addAt: null, pop: null, assist: null, sideBusy: null,
    editTitle: null, editSub: null, hoverStep: null, userMenu: false,
  },
  samples: {},            // element id → {sig, loading, data, error}
  tryRuns: {},            // case id → draft signature a Try-it run started from
  playInfo: null,         // share-link page: {case, title, published, is_owner}
  playError: '',
  toast: null,            // {text, kind, action, actionLabel}
  dialog: null,           // {title, intro, items, actions:[{label, primary, run}]}
  vw: window.innerWidth,
});

const systemKeys = computed(() => new Set(store.systemFields.map(([k]) => k)));
const strategyCatalog = computed(() => Object.fromEntries((store.pack?.strategies || []).map(s => [s.key, s])));
const dirty = computed(() => !!store.doc && JSON.stringify(store.doc) !== store.saved);
const sentence = computed(() => (store.doc ? M.phaseSentence(store.doc.steps) : ''));
const has = t => !!(t || '').trim();
const tok = key => `{{${key}}}`;

// ── helpers ──────────────────────────────────────────────────────────────────

async function api(path, { method = 'GET', body } = {}) {
  const r = await apiFetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await r.json(); } catch { /* empty body */ }
  if (!r.ok) {
    const err = new Error(data?.detail || (data && JSON.stringify(data)) || `Request failed (${r.status})`);
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data;
}

let toastTimer = null;
function toast(text, { kind = 'info', action = null, actionLabel = 'Undo', ms = 6000 } = {}) {
  clearTimeout(toastTimer);
  store.toast = { text, kind, action, actionLabel };
  toastTimer = setTimeout(() => { store.toast = null; }, ms);
}

/** Snapshot the document so the next change can be undone from a toast. */
function withUndo(label, change) {
  const snapshot = JSON.stringify(store.doc);
  change();
  toast(label, { action: () => { store.doc = JSON.parse(snapshot); store.toast = null; } });
}

function closePops() {
  store.ui.pop = null;
  store.ui.stepMenu = null;
  store.ui.userMenu = false;
}

function openPop(elId, type) {
  const same = store.ui.pop && store.ui.pop.el === elId && store.ui.pop.type === type;
  closePops();
  store.ui.addAt = null;
  if (!same) store.ui.pop = { el: elId, type };
}

function relativeTime(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

const STATUS_LABEL = { draft: 'draft', published: 'published', changed: 'edited' };

// ── case lifecycle ───────────────────────────────────────────────────────────

function resetUi() {
  Object.assign(store.ui, {
    openStep: store.doc?.steps[0]?.id || null, tplOpen: false, stepMenu: null, addAt: null,
    pop: null, assist: null, sideBusy: null, editTitle: null, editSub: null,
  });
  store.samples = {};
}

function setCurrent(data) {
  store.current = { id: data.id, revision: data.revision, status: data.status };
  store.doc = M.ensureCaseDefaults(data.document, store.pack);
  store.saved = JSON.stringify(data.document);
  store.view = 'editor';
  store.mode = 'author';
  lsSet(LS_LAST_CASE, data.id);
  resetUi();
}

function confirmDiscard() {
  return !dirty.value || window.confirm('You have unsaved changes in this case. Discard them?');
}

async function refreshCases() {
  store.cases = await api('/vp/api/cases/');
}

async function startCase(templateId) {
  if (!confirmDiscard()) return;
  try {
    const data = await api('/vp/api/cases/', { method: 'POST', body: { document: M.newCase(store.pack, templateId) } });
    setCurrent(data);
    refreshCases();
  } catch (e) {
    toast(`Could not create the case: ${e.message}`, { kind: 'error' });
  }
}

async function openCase(id) {
  if (store.current?.id === id && store.doc) { store.view = 'editor'; return; }
  if (!confirmDiscard()) return;
  try {
    setCurrent(await api(`/vp/api/cases/${id}/`));
  } catch (e) {
    toast(`Could not open the case: ${e.message}`, { kind: 'error' });
  }
}

async function deleteCase(c) {
  if (!window.confirm(`Delete “${c.title || 'Untitled case'}”? This can’t be undone.`)) return;
  try {
    await api(`/vp/api/cases/${c.id}/`, { method: 'DELETE' });
    if (store.current?.id === c.id) { store.current = null; store.doc = null; store.saved = ''; }
    await refreshCases();
  } catch (e) {
    toast(`Could not delete the case: ${e.message}`, { kind: 'error' });
  }
}

async function save({ quiet = false } = {}) {
  if (!store.doc || store.saving) return false;
  store.saving = true;
  const snapshot = JSON.stringify(store.doc);
  try {
    const data = await api(`/vp/api/cases/${store.current.id}/`, {
      method: 'PUT', body: { document: JSON.parse(snapshot), base_revision: store.current.revision },
    });
    store.current.revision = data.revision;
    store.current.status = data.status;
    store.saved = snapshot;
    refreshCases();
    if (!quiet) toast('Saved.', { ms: 2000 });
    return true;
  } catch (e) {
    if (e.status === 409) {
      store.dialog = {
        title: 'Saved from another window',
        intro: 'This case was changed and saved elsewhere since you opened it. Reload it to continue from the saved version — your unsaved changes here will be lost.',
        actions: [
          { label: 'Keep editing', run: () => { store.dialog = null; } },
          { label: 'Reload case', primary: true, run: async () => {
            store.dialog = null; store.saved = JSON.stringify(store.doc);
            setCurrent(await api(`/vp/api/cases/${store.current.id}/`));
          } },
        ],
      };
    } else {
      toast(`Could not save: ${e.message}`, { kind: 'error' });
    }
    return false;
  } finally {
    store.saving = false;
  }
}

function showProblems(problems) {
  store.dialog = {
    title: 'Not ready to publish',
    intro: 'Students would meet these gaps. Fix them, then publish again.',
    items: problems,
    actions: [{ label: 'Close', primary: true, run: () => { store.dialog = null; } }],
  };
}

async function publish() {
  if (!store.doc) return;
  const problems = M.publishProblems(store.doc, systemKeys.value);
  if (problems.length) { showProblems(problems); return; }
  if (dirty.value && !(await save({ quiet: true }))) return;
  try {
    const data = await api(`/vp/api/cases/${store.current.id}/publish/`, { method: 'POST' });
    store.current.status = data.status;
    refreshCases();
    const id = store.current.id;
    toast(`Published v${data.published_revision}.`, {
      action: () => copyStudentLink(id), actionLabel: 'Copy student link', ms: 8000,
    });
  } catch (e) {
    if (e.status === 400 && e.data?.problems) showProblems(e.data.problems);
    else toast(`Could not publish: ${e.message}`, { kind: 'error' });
  }
}

// ── components ───────────────────────────────────────────────────────────────

const PopItem = {
  props: { icon: String, label: String, desc: String, checked: Boolean, disabled: Boolean, iconColor: String },
  emits: ['pick'],
  template: `
    <button class="pop-item" :class="{checked}" :disabled="disabled" @click="$emit('pick')">
      <i class="ti" :class="icon" :style="iconColor && !disabled ? {color: iconColor} : null"></i>
      <span class="pi-body"><span>[[ label ]]</span><span v-if="desc" class="pi-desc">[[ desc ]]</span></span>
      <i v-if="checked" class="ti ti-check pi-check"></i>
    </button>`,
};

const UserMenu = {
  setup() {
    function out() { signOut(); window.location.href = '/'; }
    return { store, out };
  },
  template: `
  <div class="user-menu-wrap" data-pop>
    <button class="user-btn" :title="store.user?.email" @click="store.ui.userMenu = !store.ui.userMenu">
      <img v-if="store.user?.picture" :src="store.user.picture" alt="" referrerpolicy="no-referrer">
      <i v-else class="ti ti-user"></i>
    </button>
    <div class="popover" v-if="store.ui.userMenu" style="right:0;top:38px;min-width:200px">
      <div class="pop-head">[[ store.user?.email ]]</div>
      <a class="pop-item" href="/" style="text-decoration:none"><i class="ti ti-apps"></i><span class="pi-body">Mundorum home</span></a>
      <button class="pop-item" @click="out"><i class="ti ti-logout"></i><span class="pi-body">Sign out</span></button>
    </div>
  </div>`,
};

const Topbar = {
  components: { UserMenu },
  setup() {
    const fileName = computed(() => `${M.slug(store.doc?.title) || 'untitled'}.vp`);
    const version = computed(() => store.current
      ? `v${store.current.revision} ${STATUS_LABEL[store.current.status] || ''}` : '');
    function newCase() {
      store.mode = 'author';
      store.view = 'gallery';
      closePops();
    }
    function tryIt() { store.mode = 'player'; closePops(); }
    return { store, fileName, version, dirty, newCase, tryIt, save, publish };
  },
  template: `
  <header class="topbar">
    <a class="logo" href="/vp/"><span class="logo-tile">vp</span><span class="logo-text">vp-studio</span></a>
    <template v-if="store.doc">
      <span class="file-name">[[ fileName ]]</span>
      <span class="version-tag">[[ version ]]</span>
      <span class="unsaved" v-if="store.saving">Saving…</span>
      <span class="unsaved" v-else-if="dirty">Unsaved changes</span>
    </template>
    <button class="btn-new" @click="newCase"><i class="ti ti-plus"></i><span>New case</span></button>
    <div class="editor-mode">
      <span>Editor</span>
      <div class="seg">
        <button class="on">Simple</button>
        <button disabled title="Advanced mode is coming soon">Advanced</button>
      </div>
    </div>
    <div class="spacer"></div>
    <div class="tabs">
      <button :class="{on: store.mode === 'author'}" @click="store.mode = 'author'"><i class="ti ti-pencil"></i><span>Author</span></button>
      <button :class="{on: store.mode === 'player'}" @click="tryIt"><i class="ti ti-player-play"></i><span>Player</span></button>
    </div>
    <div class="spacer"></div>
    <button class="btn-ghost" :disabled="!store.doc || !dirty || store.saving" @click="save()" title="Save (Ctrl+S)">
      <i class="ti ti-device-floppy"></i><span>Save</span></button>
    <button class="btn-primary" :disabled="!store.doc" @click="publish"><i class="ti ti-rocket"></i><span>Publish</span></button>
    <UserMenu />
  </header>`,
};

const GalleryView = {
  setup() {
    const C = id => M.STEP_TYPES[id].color;
    const templates = computed(() => store.pack.templates.map(t => {
      const types = ['welcome', ...t.steps, 'final'];
      return { ...t, icons: types.map(x => ({ icon: M.STEP_TYPES[x].icon, color: C(x) })), n: `${types.length} steps` };
    }));
    function back() { store.view = 'editor'; }
    return { store, templates, startCase, openCase, deleteCase, back, relativeTime, STATUS_LABEL, copyStudentLink };
  },
  template: `
  <div class="gallery">
    <div class="gallery-head">
      <div>
        <h1>Start a new virtual patient</h1>
        <span class="gallery-sub">Pick a script to begin with, or build the steps yourself. You can change everything later.</span>
      </div>
      <button v-if="store.doc" class="btn-back" @click="back"><i class="ti ti-arrow-left"></i>Back to current case</button>
    </div>
    <div v-if="store.pack.placeholder" class="placeholder-note">
      <i class="ti ti-info-circle"></i>
      <span>These scripts and default texts are neutral placeholders. A deployment loads its own with <code>manage.py load_vp_content</code>.</span>
    </div>
    <button class="scratch" @click="startCase(null)">
      <span class="tile c-accent"><i class="ti ti-file-plus"></i></span>
      <span class="scratch-body"><b>Start from scratch</b><span>Only Welcome and Final feedback. Add the steps in between yourself.</span></span>
      <i class="ti ti-arrow-right"></i>
    </button>
    <div class="eyebrow" style="margin-top:6px">Or start from a script</div>
    <div class="tpl-grid">
      <button v-for="t in templates" :key="t.id" class="tpl-card" @click="startCase(t.id)">
        <span class="tpl-icons">
          <span v-for="(ic, i) in t.icons" :key="i" class="tile" :class="'c-' + ic.color"><i class="ti" :class="ic.icon"></i></span>
          <span class="tpl-n">[[ t.n ]]</span>
        </span>
        <span class="tpl-name">[[ t.name ]]</span>
        <span class="tpl-desc">[[ t.description ]]</span>
      </button>
    </div>
    <template v-if="store.cases.length">
      <div class="eyebrow" style="margin-top:14px">Your cases</div>
      <div class="case-list">
        <div v-for="c in store.cases" :key="c.id" class="case-row" :class="{current: store.current?.id === c.id}">
          <button class="case-open" @click="openCase(c.id)">
            <span class="case-title" :class="{untitled: !c.title}">[[ c.title || 'Untitled case' ]]</span>
            <span class="case-meta">v[[ c.revision ]] · [[ STATUS_LABEL[c.status] ]] · [[ relativeTime(c.updated_at) ]]</span>
          </button>
          <button v-if="c.published_revision != null" class="icon-btn" title="Copy student link" @click="copyStudentLink(c.id)"><i class="ti ti-link"></i></button>
          <button class="icon-btn" title="Delete case" @click="deleteCase(c)"><i class="ti ti-trash"></i></button>
        </div>
      </div>
    </template>
  </div>`,
};

// The highlighting prompt editor (§6.2) with its Insert-field tray (§6.3).
const caretPos = new Map();

const PromptEditor = {
  // `field` is the element property being edited: the prompt ('text') or
  // the interaction's end condition ('endsWhen', optional — no empty warning).
  props: { el: Object, stepIndex: Number, field: { type: String, default: 'text' } },
  setup(props) {
    const input = ref(null);
    const id = computed(() => `${props.el.id}:${props.field}`);
    const value = computed(() => props.el[props.field] || '');
    const optional = computed(() => props.field !== 'text');
    const status = key => M.fieldStatus(key, store.doc, props.stepIndex, systemKeys.value);
    const segments = computed(() => {
      const text = value.value;
      const segs = M.splitFields(text).map(s => (s.key ? { ...s, cls: `f-${status(s.key)}` } : s));
      if (!text || text.endsWith('\n')) segs.push({ text: ' ' });
      return segs;
    });
    const issues = computed(() => {
      const seen = new Set();
      return M.fieldsIn(value.value).filter(k => !seen.has(k) && seen.add(k))
        .map(k => ({ key: k, status: status(k) })).filter(f => f.status !== 'known');
    });
    const trayOpen = computed(() => store.ui.pop?.el === id.value && store.ui.pop?.type === 'fields');
    const fields = computed(() => M.availableFields(store.doc, props.stepIndex, store.systemFields));
    const hint = computed(() => {
      if (optional.value) return 'Checked by the LLM after each student turn. Leave empty to stop only at the turn limit.';
      return props.el.kind === 'generated' ? 'Written fresh in every session' : 'Runs in turns until it ends (see below)';
    });
    const placeholder = computed(() => {
      if (optional.value) return 'e.g. The student has explained the main mechanisms in their own words.';
      return props.el.kind === 'generated'
        ? 'Write the instructions the LLM follows to produce this text…'
        : 'Describe how the agent should interact with the student…';
    });
    function track(e) { caretPos.set(id.value, e.target.selectionStart); }
    function onInput(e) { props.el[props.field] = e.target.value; track(e); }
    function insert(key) {
      const [text, caret] = M.insertField(value.value, caretPos.get(id.value), key);
      props.el[props.field] = text;
      caretPos.set(id.value, caret);
      nextTick(() => { input.value?.focus(); input.value?.setSelectionRange(caret, caret); });
    }
    return { store, input, id, value, optional, segments, issues, trayOpen, fields, hint, placeholder,
             onInput, track, insert, openPop, tok, has };
  },
  template: `
  <div class="prompt-box" :class="{empty: !optional && !has(value), compact: optional}">
    <pre class="prompt-mirror" aria-hidden="true"><span v-for="(s, i) in segments" :key="i" :class="s.cls">[[ s.text ]]</span></pre>
    <textarea ref="input" class="prompt-input" :value="value" :placeholder="placeholder" spellcheck="false"
              @input="onInput" @select="track" @click="track" @keyup="track"></textarea>
  </div>
  <div class="prompt-tools">
    <button class="insert-field" :class="{on: trayOpen}" @click="openPop(id, 'fields')"><i class="ti ti-braces"></i>Insert field</button>
    <span class="prompt-hint">[[ hint ]]</span>
  </div>
  <div class="field-tray" v-if="trayOpen">
    <button v-for="f in fields" :key="f.key" :title="f.desc" @click="insert(f.key)">[[ tok(f.key) ]]</button>
  </div>
  <div class="field-issues" v-if="issues.length">
    <div v-for="f in issues" :key="f.key"><i class="ti ti-alert-triangle"></i>
      <span><code>[[ tok(f.key) ]]</code> [[ f.status === 'forward' ? 'refers to something that doesn’t exist yet at this step' : 'is not a known field' ]]</span>
    </div>
  </div>`,
};

// Interaction exit settings: "Ends when…", turn limit, "I'm done" switch.
const EndsBlock = {
  components: { PromptEditor },
  props: { el: Object, stepIndex: Number },
  setup(props) {
    const turns = ref(props.el.maxTurns);
    watch(() => props.el.maxTurns, v => { turns.value = v; });
    function commitTurns() {
      const n = Math.round(Number(turns.value));
      props.el.maxTurns = Number.isFinite(n) && n >= M.MIN_TURNS
        ? Math.min(n, M.MAX_TURNS) : (props.el.maxTurns || M.DEFAULT_MAX_TURNS);
      turns.value = props.el.maxTurns;
    }
    return { M, turns, commitTurns };
  },
  template: `
  <div class="ends-block">
    <span class="ends-head"><i class="ti ti-flag-check"></i>Ends when…</span>
    <PromptEditor :el="el" :step-index="stepIndex" field="endsWhen" />
    <div class="ends-row">
      <label class="turns">Max turns
        <input type="number" :min="M.MIN_TURNS" :max="M.MAX_TURNS" v-model="turns" @change="commitTurns" @blur="commitTurns"
               aria-label="Maximum number of student turns"></label>
      <button class="switch-btn" @click="el.allowStudentExit = !el.allowStudentExit"
              title="Shows an “I’m done” button in the player after the student’s first reply">
        <span class="switch" :class="{on: el.allowStudentExit}"></span><span>Students can say they’re done</span></button>
    </div>
  </div>`,
};

const ASSIST_MODES = {
  text: { title: 'Write this text', placeholder: 'What should it say? e.g. a warm two-sentence welcome', button: 'Generate text', icon: 'ti-wand' },
  vignette: { title: 'Generate a case vignette', placeholder: 'Describe the patient, or leave empty to use the patient dataset', button: 'Generate vignette', icon: 'ti-stethoscope' },
  prompt: { title: 'Write the prompt', placeholder: 'Describe what the agent should do, in your own words', button: 'Draft prompt', icon: 'ti-wand' },
  vprompt: { title: 'Prompt for a case vignette', placeholder: 'Which mechanisms should the case test?', button: 'Draft prompt', icon: 'ti-stethoscope' },
};

const ASSIST_BUTTONS = {
  literal: [['text', 'ti-wand', 'Write this text with the assistant'],
            ['vignette', 'ti-stethoscope', 'Generate a case presentation vignette']],
  generated: [['prompt', 'ti-wand', 'Write the prompt with the assistant'],
              ['vprompt', 'ti-stethoscope', 'Write a prompt that generates a case vignette']],
  interaction: [['prompt', 'ti-wand', 'Write the interaction prompt with the assistant']],
};

const ElementCard = {
  components: { PromptEditor, EndsBlock, PopItem },
  props: ['step', 'stepIndex', 'el', 'elIndex'],
  setup(props) {
    const kind = computed(() => M.ELEMENT_KINDS[props.el.kind]);
    const pop = computed(() => (store.ui.pop?.el === props.el.id ? store.ui.pop.type : null));
    const assist = computed(() => (store.ui.assist?.el === props.el.id ? store.ui.assist : null));
    const assistMode = computed(() => assist.value && ASSIST_MODES[assist.value.mode]);
    const rows = computed(() => {
      if (props.el.card) return 6;
      const lines = (props.el.text || '').split('\n').reduce((n, l) => n + Math.max(1, Math.ceil(l.length / 72)), 0);
      return Math.min(9, Math.max(2, lines));
    });
    const strategyGroups = computed(() => M.STRATEGY_CATEGORIES[props.el.kind].map(cat => ({
      cat, items: store.pack.strategies.filter(s => s.category === cat),
    })));
    const chips = computed(() => props.el.strategies.map(s => ({ s, spec: strategyCatalog.value[s.key] })).filter(c => c.spec));
    const activeKeys = computed(() => new Set(props.el.strategies.map(s => s.key)));
    const elements = computed(() => props.step.elements);

    function setKind(k) { M.setElementKind(props.el, k, strategyCatalog.value); store.ui.pop = null; }
    function move(d) { M.moveElement(props.step, props.elIndex, props.elIndex + d); store.ui.pop = null; }
    function remove() {
      store.ui.pop = null;
      withUndo('Element removed.', () => props.step.elements.splice(props.elIndex, 1));
    }
    function attach(preset) { M.addSideInfo(store.doc, props.step, props.stepIndex, props.el, preset); store.ui.pop = null; }
    function toggleStrat(key) { M.toggleStrategy(props.el, key, strategyCatalog.value); }
    function editPrompts() {
      const first = props.el.strategies[0];
      store.ui.pop = null;
      store.ui.stratOpen = true;
      if (first) store.ui.stratSel = `strategy:${first.key}`;
      nextTick(() => document.querySelector('.strat-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    }
    function removeStrat(key) { props.el.strategies = props.el.strategies.filter(s => s.key !== key); }
    function removeSide(side) {
      withUndo('Side information removed.', () => { props.el.sideInfo = props.el.sideInfo.filter(x => x.id !== side.id); });
    }
    function toggleAssist(mode) {
      closePops();
      store.ui.assist = assist.value?.mode === mode ? null : { el: props.el.id, mode, text: '', busy: false, error: '' };
    }
    async function runAssist() {
      const a = store.ui.assist;
      if (!a || a.busy) return;
      a.busy = true;
      a.error = '';
      try {
        const { text } = await api('/vp/api/assist/', { method: 'POST', body: {
          mode: a.mode, document: store.doc, step: props.step.id, element: props.el.id, instruction: a.text,
        } });
        withUndo('Text replaced by the assistant.', () => { props.el.text = text; });
        store.ui.assist = null;
      } catch (e) {
        a.error = e.message;
      } finally {
        a.busy = false;
      }
    }
    async function generateExpert(side) {
      if (store.ui.sideBusy) return;
      store.ui.sideBusy = side.id;
      try {
        const { text } = await api('/vp/api/assist/', { method: 'POST', body: {
          mode: 'expert', document: store.doc, step: props.step.id, element: props.el.id, side: side.id,
        } });
        withUndo('Expert explanation written by the assistant.', () => { side.text = text; });
      } catch (e) {
        toast(e.message, { kind: 'error' });
      } finally {
        store.ui.sideBusy = null;
      }
    }
    return {
      store, M, kind, pop, assist, assistMode, rows, strategyGroups, chips, activeKeys, elements, sentence,
      ASSIST_BUTTONS, has, tok, openPop, setKind, move, remove, attach, toggleStrat, editPrompts, removeStrat, removeSide,
      toggleAssist, runAssist, generateExpert, cycle: M.cycleMoment,
    };
  },
  template: `
  <div class="el-card" :class="el.kind">
    <div class="el-head">
      <button class="kind-badge" :class="'c-' + kind.color" title="Change element type" data-pop @click="openPop(el.id, 'kind')">
        <i class="ti" :class="kind.icon"></i>[[ kind.label ]]<i class="ti ti-chevron-down"></i>
      </button>
      <input class="el-label" v-model="el.label" aria-label="Element name">
      <div class="el-tools">
        <button v-for="[mode, icon, title] in ASSIST_BUTTONS[el.kind]" :key="mode" class="icon-btn assist"
                :class="{on: assist?.mode === mode}" :title="title" @click="toggleAssist(mode)"><i class="ti" :class="icon"></i></button>
        <span class="divider"></span>
        <button class="count-btn attach" :class="{on: pop === 'attach'}" title="Attach side information for the agent" data-pop
                @click="openPop(el.id, 'attach')"><i class="ti ti-paperclip"></i>[[ el.sideInfo.length || '' ]]</button>
        <button class="count-btn strat" :class="{on: pop === 'strat'}" title="Strategies" data-pop
                @click="openPop(el.id, 'strat')"><i class="ti ti-puzzle"></i>[[ el.strategies.length || '' ]]</button>
        <button class="icon-btn menu" :class="{on: pop === 'menu'}" title="Element options" data-pop
                @click="openPop(el.id, 'menu')"><i class="ti ti-dots-vertical"></i></button>
      </div>
    </div>

    <div v-if="pop && pop !== 'fields'" class="popover el-pop" :class="pop === 'kind' ? 'left' : 'right'" data-pop>
      <template v-if="pop === 'kind'">
        <PopItem v-for="(k, key) in M.ELEMENT_KINDS" :key="key" :icon="k.icon" :label="k.name" :desc="k.desc"
                 :checked="el.kind === key" :icon-color="k.color === 'accent' ? 'var(--c-accent)' : 'var(--c-tag-' + k.color + ')'"
                 @pick="setKind(key)" />
      </template>
      <template v-else-if="pop === 'menu'">
        <PopItem icon="ti-arrow-up" label="Move up" :desc="elIndex === 0 ? 'Already first' : ''" :disabled="elIndex === 0" @pick="move(-1)" />
        <PopItem icon="ti-arrow-down" label="Move down" :desc="elIndex === elements.length - 1 ? 'Already last' : ''"
                 :disabled="elIndex === elements.length - 1" @pick="move(1)" />
        <PopItem icon="ti-trash" label="Remove element" @pick="remove" />
      </template>
      <template v-else-if="pop === 'attach'">
        <div class="pop-head">Attach side information</div>
        <PopItem v-for="p in M.SIDE_PRESETS" :key="p.label" :icon="p.icon" :label="p.label" :desc="p.desc"
                 icon-color="var(--c-tag-place)" @pick="attach(p)" />
      </template>
      <template v-else-if="pop === 'strat'">
        <template v-for="g in strategyGroups" :key="g.cat">
          <div class="pop-head">[[ g.cat ]]</div>
          <PopItem v-for="s in g.items" :key="s.key" :icon="s.icon" :label="s.name" :desc="s.description + ' · ' + s.moment"
                   :checked="activeKeys.has(s.key)" icon-color="var(--c-tag-state)" @pick="toggleStrat(s.key)" />
        </template>
        <PopItem icon="ti-edit" label="Edit strategy prompts" desc="Opens the Strategies panel" @pick="editPrompts" />
      </template>
    </div>

    <div v-if="assist" class="assist-bar">
      <i class="ti" :class="assistMode.icon"></i><b>[[ assistMode.title ]]</b>
      <input v-model="assist.text" :placeholder="assistMode.placeholder" @keydown.enter="runAssist" :disabled="assist.busy">
      <button class="assist-run" :disabled="assist.busy" @click="runAssist">[[ assist.busy ? 'Generating…' : assistMode.button ]]</button>
      <button class="assist-close" title="Close" @click="store.ui.assist = null"><i class="ti ti-x"></i></button>
      <span class="assist-error" v-if="assist.error">[[ assist.error ]]</span>
    </div>

    <div class="el-body">
      <textarea v-if="el.kind === 'literal'" class="literal-text" :class="{empty: !has(el.text)}" v-model="el.text" :rows="rows"
                placeholder="Write the text the student will read…"></textarea>
      <PromptEditor v-else :el="el" :step-index="stepIndex" />
      <EndsBlock v-if="el.kind === 'interaction'" :el="el" :step-index="stepIndex" />
      <div class="info-line" v-if="el.autoPhaseSentence && sentence">
        <i class="ti ti-link link-ic"></i><span>Added automatically from the steps: <q>[[ sentence ]]</q></span>
      </div>
      <div class="info-line" v-if="el.note"><i class="ti ti-info-circle"></i><span>[[ el.note ]]</span></div>
      <div class="info-line" v-if="el.reviewMaterials"><i class="ti ti-books"></i>
        <span>Followed by the case vignettes, expert explanations and knowledge text, for review.</span></div>
      <div class="strat-chips" v-if="chips.length">
        <span class="strat-chip" v-for="c in chips" :key="c.s.key">
          <i class="ti" :class="c.spec.icon"></i><b>[[ c.spec.name ]]</b>
          <button class="moment" title="When it acts — click to change" @click="cycle(c.s)">[[ c.s.moment ]]</button>
          <button class="x" title="Remove strategy" @click="removeStrat(c.s.key)"><i class="ti ti-x"></i></button>
        </span>
      </div>
    </div>

    <div class="side-block" v-if="el.sideInfo.length">
      <span class="side-head"><i class="ti ti-eye-off"></i>Side information · guides the agent, never shown</span>
      <div class="side-item" v-for="side in el.sideInfo" :key="side.id">
        <div class="side-item-head">
          <i class="ti ti-paperclip"></i>
          <input class="side-label" v-model="side.label" aria-label="Side information name">
          <span class="side-ref">[[ tok(side.ref) ]]</span>
          <button v-if="side.generateFromCase" class="side-gen" :disabled="!!store.ui.sideBusy" title="Generate with the assistant"
                  @click="generateExpert(side)"><i class="ti ti-wand"></i>[[ store.ui.sideBusy === side.id ? 'Generating…' : 'Generate from knowledge text' ]]</button>
          <button class="side-x" title="Remove" @click="removeSide(side)"><i class="ti ti-x"></i></button>
        </div>
        <textarea class="side-text" :class="{empty: !has(side.text)}" v-model="side.text" rows="4" placeholder="Only the agent sees this…"></textarea>
      </div>
    </div>
  </div>`,
};

const StepCard = {
  components: { ElementCard, PopItem },
  props: ['step', 'index'],
  setup(props) {
    const steps = computed(() => store.doc.steps);
    const spec = computed(() => M.STEP_TYPES[props.step.type]);
    const open = computed(() => store.ui.openStep === props.step.id);
    const last = computed(() => props.index === steps.value.length - 1);
    const ready = computed(() => M.stepRequirements(props.step).every(Boolean));
    const name = computed(() => M.stepName(props.step));
    const purpose = computed(() => M.stepPurpose(props.step));
    const summary = computed(() => (open.value ? purpose.value : M.collapsedSummary(props.step)));
    const editingTitle = computed(() => store.ui.editTitle === props.step.id);
    const editingSub = computed(() => store.ui.editSub === props.step.id);
    const menuOpen = computed(() => store.ui.stepMenu === props.step.id);
    const addOpen = computed(() => store.ui.addAt === props.step.id);
    const titleInput = ref(null);
    const subInput = ref(null);
    const draft = ref('');
    const subDraft = ref('');
    let cancelled = false;

    const defaultName = () => M.stepName({ ...props.step, title: undefined });

    function toggleOpen() {
      closePops();
      store.ui.addAt = null;
      store.ui.openStep = open.value ? null : props.step.id;
    }
    function startEdit() {
      closePops();
      store.ui.hoverStep = null;
      draft.value = props.step.title ?? (props.step.type === 'custom' ? '' : defaultName());
      cancelled = false;
      store.ui.editTitle = props.step.id;
      nextTick(() => { titleInput.value?.focus(); titleInput.value?.select(); });
    }
    function endEdit() {
      if (store.ui.editTitle !== props.step.id) return;
      store.ui.editTitle = null;
      if (cancelled) return;
      const value = draft.value.trim();
      M.setStepTitle(store.doc, props.step.id, value === defaultName() ? '' : value);
    }
    function startSub() {
      closePops();
      subDraft.value = props.step.subtitle ?? (spec.value.sub || '');
      cancelled = false;
      store.ui.editSub = props.step.id;
      nextTick(() => subInput.value?.focus());
    }
    function endSub() {
      if (store.ui.editSub !== props.step.id) return;
      store.ui.editSub = null;
      if (!cancelled) M.setStepSubtitle(props.step, subDraft.value);
    }
    function editKey(e) {
      if (e.key === 'Enter') e.target.blur();
      if (e.key === 'Escape') { cancelled = true; e.target.blur(); }
    }
    function toggleMenu() {
      const was = menuOpen.value;
      closePops();
      store.ui.addAt = null;
      if (!was) store.ui.stepMenu = props.step.id;
    }
    function toggleAdd() {
      const was = addOpen.value;
      closePops();
      store.ui.addAt = was ? null : props.step.id;
    }

    const fixed = computed(() => ['welcome', 'final'].includes(props.step.type));
    const upReason = computed(() => M.moveBlockReason(steps.value, props.index, props.index - 1));
    const downReason = computed(() => M.moveBlockReason(steps.value, props.index, props.index + 1));
    const removeReason = computed(() => M.removeBlockReason(steps.value, props.index));
    function run(fn) { store.ui.stepMenu = null; fn(); }
    function move(d) { run(() => M.moveStep(store.doc, props.index, props.index + d)); }
    function duplicateTransfer() {
      run(() => {
        const s = M.insertStep(store.doc, store.pack, props.index, 'transfer');
        store.ui.openStep = s.id;
      });
    }
    function removeStep() {
      run(() => withUndo(`“${name.value}” removed.`, () => M.removeStep(store.doc, props.index)));
    }

    const addOptions = computed(() => M.ADDABLE_TYPES.map(type => {
      const t = M.STEP_TYPES[type];
      const reason = M.insertBlockReason(steps.value, props.index, type);
      const label = type === 'transfer' ? `Transfer to case ${M.nextCaseN(steps.value)}` : (t.addName || t.name);
      return { type, label, icon: t.icon, color: t.color, desc: reason || t.addDesc, disabled: !!reason };
    }));
    function addStep(type) {
      const s = M.insertStep(store.doc, store.pack, props.index, type);
      store.ui.addAt = null;
      store.ui.openStep = s.id;
      if (type === 'custom') {
        nextTick(() => {
          store.ui.editTitle = s.id;
          // the new card's own startEdit isn't reachable from here; focus by id
          nextTick(() => document.querySelector(`[data-title-input="${s.id}"]`)?.focus());
        });
      }
    }
    function addElement(kind) { props.step.elements.push(M.newElement(kind)); }

    return {
      store, M, spec, open, last, ready, name, purpose, summary, editingTitle, editingSub, menuOpen, addOpen,
      titleInput, subInput, draft, subDraft, fixed, upReason, downReason, removeReason, addOptions, tok,
      toggleOpen, startEdit, endEdit, startSub, endSub, editKey, toggleMenu, toggleAdd, move, duplicateTransfer,
      removeStep, addStep, addElement, startRename: () => run(startEdit), startSubtitle: () => run(startSub),
    };
  },
  template: `
  <div class="step-row">
    <div class="rail">
      <span class="rail-dot" :class="{on: open}">[[ index ]]</span>
      <span class="rail-line" v-if="!last"></span>
    </div>
    <div class="step-col">
      <div class="step-card" :class="{open}">
        <div class="step-head">
          <div class="step-head-main" @click="toggleOpen">
            <span class="tile" :class="'c-' + spec.color"><i class="ti" :class="spec.icon"></i></span>
            <span class="step-titles">
              <input v-if="editingTitle" ref="titleInput" :data-title-input="step.id" class="step-title-input" v-model="draft"
                     placeholder="Name this step" @click.stop @keydown="editKey" @blur="endEdit">
              <span v-else class="step-title" :class="{untitled: step.type === 'custom' && !step.title}"
                    @click.stop="startEdit" @mouseenter="store.ui.hoverStep = step.id"
                    @mouseleave="store.ui.hoverStep === step.id && (store.ui.hoverStep = null)">[[ name ]]</span>
              <input v-if="editingSub" ref="subInput" class="step-sub-input" v-model="subDraft"
                     placeholder="What is this step for? Shown when hovering the title" @click.stop @keydown="editKey" @blur="endSub">
              <span v-else-if="!open" class="step-summary">[[ summary ]]</span>
            </span>
            <span class="status-pill" :class="ready ? 'c-text' : 'c-state'">[[ ready ? 'Ready' : 'Needs input' ]]</span>
            <i class="ti step-chev" :class="open ? 'ti-chevron-up' : 'ti-chevron-down'"></i>
          </div>
          <button class="step-menu-btn" :class="{on: menuOpen}" title="Step options" data-pop @click="toggleMenu"><i class="ti ti-dots"></i></button>
        </div>
        <div class="tooltip" v-if="store.ui.hoverStep === step.id && !editingTitle">[[ purpose ]]</div>
        <div class="popover step-menu" v-if="menuOpen" data-pop>
          <PopItem icon="ti-pencil" label="Rename" @pick="startRename" />
          <PopItem icon="ti-text-caption" label="Edit subtitle" @pick="startSubtitle" />
          <template v-if="fixed">
            <PopItem icon="ti-arrows-sort" label="Move" disabled
                     :desc="step.type === 'welcome' ? 'Welcome is always the first step' : 'Final feedback is always the last step'" />
            <PopItem icon="ti-trash" label="Remove" disabled desc="This step is always included" />
          </template>
          <template v-else>
            <PopItem icon="ti-arrow-up" label="Move up" :disabled="!!upReason" :desc="upReason" @pick="move(-1)" />
            <PopItem icon="ti-arrow-down" label="Move down" :disabled="!!downReason" :desc="downReason" @pick="move(1)" />
            <PopItem v-if="step.type === 'transfer'" icon="ti-copy" label="Duplicate with a new case" @pick="duplicateTransfer" />
            <PopItem icon="ti-trash" label="Remove step" :disabled="!!removeReason" :desc="removeReason" @pick="removeStep" />
          </template>
        </div>

        <div class="step-body" v-if="open">
          <ElementCard v-for="(el, ei) in step.elements" :key="el.id" :step="step" :step-index="index" :el="el" :el-index="ei" />
          <div class="empty-step" v-if="!step.elements.length">This step is empty. Add an element below.</div>
          <div class="answer-line" v-if="step.type !== 'final'">
            <i class="ti ti-arrow-forward-up"></i><span>Later steps can use the student’s answer here as</span>
            <span class="chip-field">[[ tok(M.answerKey(step) + '.answer') ]]</span>
          </div>
          <div class="add-element">
            <span>Add element</span>
            <button v-for="(k, key) in M.ELEMENT_KINDS" :key="key" :class="'k-' + key" :title="k.desc" @click="addElement(key)">
              <i class="ti" :class="k.icon"></i>[[ k.name ]]</button>
          </div>
        </div>
      </div>

      <div class="add-step" v-if="!last">
        <button class="add-step-btn" :class="{on: addOpen}" @click="toggleAdd"><i class="ti ti-plus"></i>Add step here</button>
        <div class="panel add-step-panel" v-if="addOpen">
          <button v-for="o in addOptions" :key="o.type" :disabled="o.disabled" @click="addStep(o.type)">
            <span class="tile" :class="o.disabled ? 'c-disabled' : 'c-' + o.color"><i class="ti" :class="o.icon"></i></span>
            <span><b>[[ o.label ]]</b><small>[[ o.desc ]]</small></span>
          </button>
        </div>
      </div>
      <div class="step-gap" v-else></div>
    </div>
  </div>`,
};

const PreviewPanel = {
  props: ['width', 'stacked'],
  setup() {
    const steps = computed(() => store.doc.steps);
    const step = computed(() => steps.value.find(s => s.id === store.ui.openStep) || steps.value[0]);
    const level = computed(() => store.doc.settings.studentLevel);

    function sigOf(el) {
      return JSON.stringify([el.text, el.strategies, level.value, el.kind, !!el.isFinalFeedback]);
    }
    function sampleFor(el) {
      const s = store.samples[el.id];
      return s && s.sig === sigOf(el) ? s : null;
    }
    async function generate(el, refresh = false) {
      const sig = sigOf(el);
      store.samples[el.id] = { sig, loading: true, data: refresh ? store.samples[el.id]?.data : null, error: '' };
      try {
        const data = await api('/vp/api/preview-sample/', { method: 'POST', body: {
          document: store.doc, step: step.value.id, element: el.id, refresh,
        } });
        store.samples[el.id] = { sig, loading: false, data, error: '' };
      } catch (e) {
        store.samples[el.id] = { sig, loading: false, data: null, error: e.message };
      }
    }

    const messages = computed(() => {
      const all = steps.value;
      const s = step.value;
      const phases = M.phaseSteps(all);
      const m = phases.length;
      const j = phases.indexOf(s) + 1;
      const out = [];
      const progress = (filled, text) => {
        if (store.doc.settings.progressBar) {
          out.push({ type: 'progress', total: m + 1, filled, pct: `${Math.round((filled / (m + 1)) * 100)}%`, text });
        }
      };
      const pn = M.phaseName(s, all);
      if (pn) {
        out.push({ type: 'phase', label: `Phase ${j}`, text: pn });
        progress(j, j === m ? 'Final stretch — time to apply your insights!' : 'Keep going — your clinical reasoning is developing!');
      }
      for (const el of s.elements) {
        if (el.kind === 'literal') {
          if (el.card) {
            out.push({ type: 'case', label: el.card, text: has(el.text) ? el.text : `${el.card} has not been written yet.`, pending: !has(el.text) });
          } else if (has(el.text)) {
            out.push({ type: 'tutor', text: el.text + (el.autoPhaseSentence && sentence.value ? `\n\n${sentence.value}` : '') });
          } else {
            out.push({ type: 'tutor', text: `${el.label} — not written yet.`, pending: true });
          }
          continue;
        }
        const sample = sampleFor(el);
        const canSample = has(el.text);
        if (el.kind === 'generated' && el.isFinalFeedback) {
          const fb = el.strategies.map(x => strategyCatalog.value[x.key]).find(x => x?.category === 'Final feedback');
          out.push({ type: 'feedback', el, label: fb?.preview_label || 'Your feedback', sample, canSample,
                     text: sample?.data?.text || (canSample ? 'Written by the LLM when the session runs.' : 'Prompt not written yet.'),
                     pending: !sample?.data });
        } else if (el.kind === 'generated') {
          out.push({ type: 'tutor', tag: 'generated', el, sample, canSample,
                     text: sample?.data?.text || (canSample ? 'Written by the LLM when the session runs.' : 'Prompt not written yet.'),
                     pending: !sample?.data });
        } else {
          if (sample?.data?.turns) {
            for (const t of sample.data.turns) {
              out.push(t.role === 'student' ? { type: 'student', text: t.text }
                : { type: 'tutor', tag: 'interaction', who: t.role === 'patient' ? 'Patient' : 'Tutor', text: t.text });
            }
            out.push({ type: 'sample-controls', el, sample, canSample });
          } else {
            out.push({ type: 'tutor', tag: 'interaction', el, sample, canSample, pending: true,
                       text: canSample ? 'The agent converses with the student following your prompt.' : 'Prompt not written yet.' });
          }
          out.push({ type: 'loop', text: `Continues in turns until it ends · at most ${el.maxTurns || M.DEFAULT_MAX_TURNS} student turns` });
        }
      }
      if (s.type === 'final') progress(m + 1, 'All phases completed! Excellent work.');
      if (!s.elements.length) out.push({ type: 'tutor', text: 'This step has no elements yet.', pending: true });
      return out;
    });

    function drag(ev) {
      ev.preventDefault();
      const x0 = ev.clientX;
      const w0 = store.ui.previewWidth;
      const moveFn = e => {
        store.ui.previewWidth = Math.max(300, Math.min(store.vw - 520, w0 + x0 - e.clientX));
      };
      const up = () => {
        window.removeEventListener('mousemove', moveFn);
        window.removeEventListener('mouseup', up);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        lsSet(LS_PREVIEW_WIDTH, String(Math.round(store.ui.previewWidth)));
      };
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      window.addEventListener('mousemove', moveFn);
      window.addEventListener('mouseup', up);
    }
    function tryIt() { store.mode = 'player'; }
    return { store, M, step, messages, generate, drag, tryIt };
  },
  template: `
  <aside class="preview" :class="{stacked}">
    <div class="pv-handle" v-if="!stacked" title="Drag to resize" @mousedown="drag"></div>
    <div class="pv-head">
      <i class="ti ti-eye"></i>
      <span>What the student sees · [[ M.stepName(step) ]]</span>
      <button class="pv-try" @click="tryIt"><i class="ti ti-player-play"></i>Try it</button>
      <button class="icon-btn" title="Hide preview" @click="store.ui.previewOpen = false"><i class="ti ti-x"></i></button>
    </div>
    <div class="pv-body">
      <template v-for="(m, i) in messages" :key="i">
        <div v-if="m.type === 'phase'" class="pv-phase"><span>[[ m.label ]]</span><b>[[ m.text ]]</b></div>
        <div v-else-if="m.type === 'progress'" class="pv-progress">
          <span class="segs"><span v-for="n in m.total" :key="n" :class="{on: n <= m.filled}"></span></span>
          <span class="pct">[[ m.pct ]]</span><span>[[ m.text ]]</span>
        </div>
        <div v-else-if="m.type === 'case'" class="pv-case">
          <div class="pv-case-head"><i class="ti ti-stethoscope"></i><span>[[ m.label ]]</span></div>
          <p :class="{'pv-text pending': m.pending}">[[ m.text ]]</p>
        </div>
        <div v-else-if="m.type === 'student'" class="pv-student">[[ m.text ]]</div>
        <div v-else-if="m.type === 'loop'" class="pv-loop"><i class="ti ti-repeat"></i>[[ m.text ]]</div>
        <div v-else-if="m.type === 'feedback'" class="pv-feedback">
          <span>[[ m.label ]]</span>
          <p :class="{'pv-text pending': m.pending}">[[ m.text ]]</p>
          <button v-if="m.canSample" class="pv-sample-btn" :disabled="m.sample?.loading" @click="generate(m.el, !!m.sample?.data)">
            <i class="ti" :class="m.sample?.data ? 'ti-refresh' : 'ti-sparkles'"></i>
            [[ m.sample?.loading ? 'Generating…' : (m.sample?.data ? 'Regenerate' : 'Generate sample') ]]</button>
          <span class="pv-error" v-if="m.sample?.error">[[ m.sample.error ]]</span>
        </div>
        <div v-else-if="m.type === 'sample-controls'" style="display:flex;gap:8px;align-items:center">
          <button class="pv-sample-btn" :disabled="m.sample?.loading" @click="generate(m.el, true)">
            <i class="ti ti-refresh"></i>[[ m.sample?.loading ? 'Generating…' : 'Regenerate' ]]</button>
          <span class="pv-error" v-if="m.sample?.error">[[ m.sample.error ]]</span>
        </div>
        <div v-else class="pv-msg">
          <span class="pv-who" :class="{patient: m.who === 'Patient'}">
            <span>[[ m.who || 'Tutor' ]]</span>
            <span v-if="m.tag === 'generated'" class="pv-tag c-char"><i class="ti ti-sparkles"></i>generated</span>
            <span v-if="m.tag === 'interaction'" class="pv-tag c-trans"><i class="ti ti-repeat"></i>interaction</span>
          </span>
          <p class="pv-text" :class="{pending: m.pending}">[[ m.text ]]</p>
          <button v-if="m.el && m.canSample && !m.sample?.data" class="pv-sample-btn" :disabled="m.sample?.loading" @click="generate(m.el)">
            <i class="ti ti-sparkles"></i>[[ m.sample?.loading ? 'Generating…' : 'Generate sample' ]]</button>
          <button v-else-if="m.el && m.sample?.data && m.tag === 'generated'" class="pv-sample-btn" :disabled="m.sample?.loading"
                  @click="generate(m.el, true)"><i class="ti ti-refresh"></i>[[ m.sample?.loading ? 'Generating…' : 'Regenerate' ]]</button>
          <span class="pv-error" v-if="m.sample?.error">[[ m.sample.error ]]</span>
        </div>
      </template>
    </div>
  </aside>`,
};

// Strategies panel (§ third toggle): one editable prompt per agent and per
// strategy, stored with the case (doc.agentPrompts / doc.strategyPrompts).
const CATEGORY_ORDER = ['Feedback', 'Final feedback', 'Patient', 'Gamification'];

const StrategiesPanel = {
  setup() {
    const groups = computed(() => [
      { name: 'Agents', items: M.AGENT_PROMPTS.map(a => ({ ...a, id: `agent:${a.key}`, kind: 'agent', color: 'accent' })) },
      ...CATEGORY_ORDER.map(cat => ({
        name: cat,
        items: store.pack.strategies.filter(x => x.category === cat).map(x => ({
          id: `strategy:${x.key}`, kind: 'strategy', key: x.key, name: x.name, icon: x.icon,
          desc: `${x.description} · default: ${x.moment}`, color: 'state',
        })),
      })).filter(g => g.items.length),
    ]);
    const items = computed(() => groups.value.flatMap(g => g.items));
    const selected = computed(() => items.value.find(i => i.id === store.ui.stratSel) || items.value[0]);
    const prompts = item => (item.kind === 'agent' ? store.doc.agentPrompts : store.doc.strategyPrompts);
    const defaultOf = item => (item.kind === 'agent' ? store.pack.agents[item.key] : strategyCatalog.value[item.key]?.instruction) || '';
    const textOf = item => prompts(item)[item.key] ?? defaultOf(item);
    const customized = item => textOf(item) !== defaultOf(item);
    const usage = computed(() => {
      const item = selected.value;
      if (!item) return '';
      if (item.kind === 'agent') {
        if (item.key === 'patient_persona') return 'Used by interviews and by interactions with a Patient strategy.';
        return item.key === 'guardrails' ? 'Used by every agent, in every turn.' : 'Used by every tutor turn and generated text.';
      }
      const where = [];
      for (const step of store.doc.steps) {
        for (const el of step.elements) {
          const s = el.strategies.find(x => x.key === item.key);
          if (s) where.push(`${M.stepName(step)} › ${el.label} (${s.moment})`);
        }
      }
      return where.length ? `Used in: ${where.join(' · ')}` : 'Not used by any element yet — attach it with the puzzle button of an element.';
    });
    function select(item) { store.ui.stratSel = item.id; }
    function setText(value) { prompts(selected.value)[selected.value.key] = value; }
    function reset() { prompts(selected.value)[selected.value.key] = defaultOf(selected.value); }
    return { store, groups, selected, textOf, customized, usage, select, setText, reset };
  },
  template: `
  <div class="panel strat-panel">
    <span class="strat-intro">Each agent and strategy has one prompt, stored with this case. Edits apply wherever it is used.</span>
    <div class="strat-groups">
      <div class="strat-group" v-for="g in groups" :key="g.name">
        <span class="eyebrow">[[ g.name ]]</span>
        <div class="strat-buttons">
          <button v-for="it in g.items" :key="it.id" :class="{on: selected?.id === it.id}" :title="it.desc" @click="select(it)">
            <span class="tile" :class="'c-' + it.color"><i class="ti" :class="it.icon"></i></span>
            <span>[[ it.name ]]</span>
            <span v-if="customized(it)" class="custom-dot" title="Edited for this case"></span>
          </button>
        </div>
      </div>
    </div>
    <div class="strat-editor" v-if="selected">
      <div class="strat-editor-head">
        <span class="tile" :class="'c-' + selected.color"><i class="ti" :class="selected.icon"></i></span>
        <span class="strat-editor-title"><b>[[ selected.name ]]</b><span>[[ selected.desc ]]</span></span>
        <button v-if="customized(selected)" class="btn-link" @click="reset"><i class="ti ti-arrow-back-up"></i>Reset to default</button>
      </div>
      <textarea class="strat-text" rows="5" :value="textOf(selected)" @input="setText($event.target.value)"
                :aria-label="selected.name + ' prompt'"></textarea>
      <span class="strat-usage">[[ usage ]]</span>
    </div>
  </div>`,
};

const EditorView = {
  components: { StepCard, PreviewPanel, StrategiesPanel },
  setup() {
    const reqs = computed(() => M.requirements(store.doc));
    const met = computed(() => reqs.value.filter(Boolean).length);
    const pw = computed(() => Math.max(300, Math.min(store.ui.previewWidth, store.vw - 520)));
    const sideBySide = computed(() => store.ui.previewOpen && store.vw >= 1100);
    const maxWidth = computed(() => (store.ui.previewOpen ? `${Math.max(1280, 880 + pw.value + 24)}px` : '880px'));
    const columns = computed(() => (sideBySide.value ? `minmax(0,1fr) ${pw.value}px` : 'minmax(0,1fr)'));
    const templateName = computed(() => store.pack.templates.find(t => t.id === store.doc.settings.scriptTemplate)?.name || 'Custom');
    const legend = [
      ['ti-quote', 'Literal · shown as written', 'accent'], ['ti-sparkles', 'Generated · the LLM writes it', 'char'],
      ['ti-repeat', 'Interaction · the agent converses', 'trans'], ['ti-paperclip', 'Side information · never shown', 'place'],
      ['ti-puzzle', 'Strategy', 'state'],
    ];
    function applyTemplate(id) {
      if (id === store.doc.settings.scriptTemplate) return;
      withUndo('Script switched.', () => M.applyTemplate(store.doc, store.pack, id));
      store.ui.openStep = store.doc.steps[0].id;
    }
    return { store, reqs, met, pw, sideBySide, maxWidth, columns, templateName, legend, applyTemplate };
  },
  template: `
  <div class="editor" :style="{maxWidth}">
    <div class="row-title">
      <input class="case-title-input" v-model="store.doc.title" placeholder="Name your virtual patient" aria-label="Case title">
      <div class="title-side">
        <div class="readiness">
          <div class="readiness-head"><span>Ready to publish</span>
            <span :class="{done: met === reqs.length}">[[ met ]] of [[ reqs.length ]]</span></div>
          <div class="readiness-bar"><span v-for="(r, i) in reqs" :key="i" :class="{met: r}"></span></div>
        </div>
        <button class="btn-toggle" :class="{on: store.ui.previewOpen}" @click="store.ui.previewOpen = !store.ui.previewOpen">
          <i class="ti ti-eye"></i>[[ store.ui.previewOpen ? 'Hide preview' : 'Preview' ]]</button>
      </div>
    </div>

    <div class="row-toggles">
      <div class="toggle-buttons">
        <button class="panel-toggle" :class="{on: store.ui.settingsOpen}" @click="store.ui.settingsOpen = !store.ui.settingsOpen">
          <i class="ti ti-adjustments-horizontal"></i><span>Case settings</span>
          <i class="ti" :class="store.ui.settingsOpen ? 'ti-chevron-up' : 'ti-chevron-down'"></i></button>
        <button class="panel-toggle" :class="{on: store.ui.legendOpen}" @click="store.ui.legendOpen = !store.ui.legendOpen">
          <i class="ti ti-category"></i><span>Element types</span>
          <i class="ti" :class="store.ui.legendOpen ? 'ti-chevron-up' : 'ti-chevron-down'"></i></button>
        <button class="panel-toggle" :class="{on: store.ui.stratOpen}" @click="store.ui.stratOpen = !store.ui.stratOpen">
          <i class="ti ti-puzzle"></i><span>Strategies</span>
          <i class="ti" :class="store.ui.stratOpen ? 'ti-chevron-up' : 'ti-chevron-down'"></i></button>
      </div>
      <div class="panel settings-panel" v-if="store.ui.settingsOpen">
        <div class="settings-row">
          <span>Students
            <span class="levels">
              <button v-for="(lv, key) in store.levels" :key="key" :class="{on: store.doc.settings.studentLevel === key}"
                      @click="store.doc.settings.studentLevel = key">[[ lv.label ]]</button>
            </span>
          </span>
          <button class="switch-btn" @click="store.doc.settings.progressBar = !store.doc.settings.progressBar">
            <span class="switch" :class="{on: store.doc.settings.progressBar}"></span><span>Progress bar</span></button>
          <span><i class="ti ti-language"></i>Replies in the student’s language</span>
          <button class="script-btn" :class="{on: store.ui.tplOpen}" @click="store.ui.tplOpen = !store.ui.tplOpen">
            <i class="ti ti-layout-list"></i>Script: [[ templateName ]]<i class="ti ti-chevron-down"></i></button>
        </div>
        <div class="tpl-switch" v-if="store.ui.tplOpen">
          <span>Switching keeps the texts of steps that stay in the script.</span>
          <div class="tpl-switch-grid">
            <button v-for="t in store.pack.templates" :key="t.id" :class="{on: store.doc.settings.scriptTemplate === t.id}"
                    @click="applyTemplate(t.id)"><b>[[ t.name ]]</b><span>[[ t.description ]]</span></button>
          </div>
        </div>
      </div>
      <div class="panel legend" v-if="store.ui.legendOpen">
        <span v-for="[icon, text, color] in legend" :key="text">
          <span class="tile" :class="'c-' + color"><i class="ti" :class="icon"></i></span>[[ text ]]</span>
      </div>
      <StrategiesPanel v-if="store.ui.stratOpen" />
    </div>

    <div class="main-grid" :style="{gridTemplateColumns: columns}">
      <div class="steps">
        <StepCard v-for="(s, i) in store.doc.steps" :key="s.id" :step="s" :index="i" />
        <div class="defaults-note"><i class="ti ti-settings-automation"></i>
          <span>Using defaults for the tutor’s persona and rules, answer checking and scoring thresholds.</span></div>
      </div>
      <PreviewPanel v-if="store.ui.previewOpen" :width="pw" :stacked="!sideBySide" />
    </div>
  </div>`,
};

// ── player ───────────────────────────────────────────────────────────────────

const PLAY_PATH = /^\/vp\/play\/([0-9a-f-]{36})\/?$/i;
const playCaseId = (window.location.pathname.match(PLAY_PATH) || [])[1] || null;
const LS_AFTER_LOGIN = 'vp.afterLogin';

function studentLink(caseId) { return `${window.location.origin}/vp/play/${caseId}/`; }

async function copyStudentLink(caseId) {
  try {
    await navigator.clipboard.writeText(studentLink(caseId));
    toast('Student link copied. Any signed-in user with the link can play the published version.', { ms: 4000 });
  } catch {
    window.prompt('Copy the student link:', studentLink(caseId));
  }
}

const PLACEHOLDERS = { answer: 'Write your answer…', pre: 'Write your answer…', interaction: 'Write your reply…' };

const PlayerView = {
  props: { mode: String, caseId: String },
  setup(props) {
    const session = ref(null);
    const error = ref('');
    const sending = ref(false);
    const draft = ref('');
    const pending = ref('');
    const scroller = ref(null);
    const input = ref(null);
    const isTry = props.mode === 'try';
    const currentSig = () => (store.doc ? JSON.stringify(store.doc) : '');
    // Try mode: the draft signature each run started from, so a changed
    // draft offers a restart. Unknown for a run resumed after a reload.
    const startedSig = computed(() => store.tryRuns[props.caseId] || null);
    const stale = computed(() => isTry && startedSig.value && startedSig.value !== currentSig());
    const published = computed(() => store.cases.find(c => c.id === props.caseId)?.published_revision != null);
    const placeholder = computed(() => PLACEHOLDERS[session.value?.waiting] || 'Please wait…');

    function scrollDown() {
      nextTick(() => { if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight; });
    }
    function focusInput() { nextTick(() => input.value?.focus()); }

    async function start(restart = false) {
      if (restart && !isTry && !window.confirm('Start this activity again from the beginning?')) return;
      error.value = '';
      sending.value = true;
      try {
        const body = { case: props.caseId, mode: props.mode, restart };
        if (isTry) body.document = store.doc;
        session.value = await api('/vp/api/sessions/', { method: 'POST', body });
        if (isTry && restart) store.tryRuns[props.caseId] = currentSig();
      } catch (e) {
        error.value = e.message;
      } finally {
        sending.value = false;
        scrollDown();
        focusInput();
      }
    }

    async function act(action, text) {
      if (!session.value || sending.value) return;
      error.value = '';
      sending.value = true;
      if (text) pending.value = text;
      scrollDown();
      try {
        session.value = await api(`/vp/api/sessions/${session.value.id}/${action}/`, {
          method: 'POST', body: text ? { text } : {},
        });
      } catch (e) {
        error.value = e.message;
        if (text) draft.value = text;       // nothing was saved: give the text back
      } finally {
        pending.value = '';
        sending.value = false;
        scrollDown();
        focusInput();
      }
    }

    function send() {
      const text = draft.value.trim();
      if (!text || !session.value?.waiting || sending.value) return;
      draft.value = '';
      act('reply', text);
    }

    onMounted(() => start(false));
    return { store, isTry, session, error, sending, draft, pending, scroller, input, stale, published, placeholder,
             start, send, act, copyStudentLink };
  },
  template: `
  <div class="player">
    <section class="chat">
      <div class="chat-scroll" ref="scroller">
        <div class="chat-inner">
          <div class="chat-title" v-if="session">
            <h1>[[ session.title ]]</h1>
            <span>[[ isTry ? 'Trying the current draft — notes in grey are visible to you only' : session.level + ' level' ]]</span>
          </div>
          <div class="stale-note" v-if="stale"><i class="ti ti-alert-circle"></i>
            <span>The case changed since this run started.</span>
            <button class="btn-link" @click="start(true)">Restart with the changes</button></div>
          <template v-for="m in session?.messages || []" :key="m.id">
            <div v-if="m.type === 'phase'" class="pv-phase"><span>[[ m.label ]]</span><b>[[ m.text ]]</b></div>
            <div v-else-if="m.type === 'progress'" class="pv-progress">
              <span class="segs"><span v-for="n in m.total" :key="n" :class="{on: n <= m.filled}"></span></span>
              <span class="pct">[[ m.pct ]]</span><span>[[ m.text ]]</span>
            </div>
            <div v-else-if="m.type === 'case'" class="pv-case">
              <div class="pv-case-head"><i class="ti ti-stethoscope"></i><span>[[ m.label ]]</span></div>
              <p>[[ m.text ]]</p>
            </div>
            <div v-else-if="m.role === 'student'" class="pv-student">[[ m.text ]]</div>
            <div v-else-if="m.type === 'feedback'" class="pv-feedback">
              <span>[[ m.label ]]</span><p>[[ m.text ]]</p>
            </div>
            <div v-else-if="m.type === 'review'" class="pv-review">
              <span class="eyebrow">Review materials</span>
              <details v-for="(it, i) in m.items" :key="i"><summary>[[ it.label ]]</summary><p>[[ it.text ]]</p></details>
            </div>
            <div v-else-if="m.type === 'notice'" class="trace-note"><i class="ti ti-info-circle"></i>[[ m.text ]]</div>
            <div v-else class="pv-msg">
              <span class="pv-who" :class="{patient: m.role === 'patient'}">
                <span>[[ m.role === 'patient' ? 'Patient' : 'Tutor' ]]</span>
                <span v-if="isTry && m.tag === 'generated'" class="pv-tag c-char"><i class="ti ti-sparkles"></i>generated</span>
                <span v-if="isTry && m.tag === 'interaction'" class="pv-tag c-trans"><i class="ti ti-repeat"></i>interaction</span>
              </span>
              <p class="pv-text">[[ m.text ]]</p>
              <span class="trace-note" v-if="m.trace">[[ m.trace ]]</span>
            </div>
          </template>
          <div v-if="pending" class="pv-student sending">[[ pending ]]</div>
          <div v-if="sending" class="typing" aria-label="Waiting for the reply"><span></span><span></span><span></span></div>
          <div class="pv-error" v-if="error" role="alert"><i class="ti ti-alert-triangle"></i> [[ error ]]</div>
        </div>
      </div>
      <div class="composer" v-if="session">
        <div class="composer-inner" v-if="!session.finished">
          <textarea ref="input" v-model="draft" rows="2" :placeholder="placeholder" :disabled="!session.waiting || sending"
                    @keydown.enter.exact.prevent="send" aria-label="Your message"></textarea>
          <div class="composer-actions">
            <button v-if="store.vw < 900" class="btn-ghost" :disabled="sending" title="Request feedback on your progress"
                    @click="act('feedback')"><i class="ti ti-message-check"></i></button>
            <button v-if="session.can_finish" class="btn-ghost" :disabled="sending" @click="act('done')"
                    title="End this part of the conversation and continue"><i class="ti ti-player-skip-forward"></i><span>I’m done with this part</span></button>
            <span class="spacer"></span>
            <button class="btn-primary" :disabled="!draft.trim() || !session.waiting || sending" @click="send">
              <i class="ti ti-send"></i><span>Send</span></button>
          </div>
        </div>
        <div class="composer-inner finished" v-else>
          <span><i class="ti ti-circle-check"></i>Activity complete.</span>
          <button class="btn-ghost" @click="start(true)"><i class="ti ti-refresh"></i><span>[[ isTry ? 'Restart' : 'Play again' ]]</span></button>
        </div>
      </div>
    </section>
    <aside class="player-side" v-if="store.vw >= 900 && session">
      <span class="eyebrow">Phases</span>
      <ol class="phase-list">
        <li v-for="(p, i) in session.phases" :key="i" :class="p.state">
          <i class="ti" :class="p.state === 'done' ? 'ti-circle-check' : p.state === 'now' ? 'ti-point-filled' : 'ti-circle'"></i>
          <span>[[ p.name ]]</span>
        </li>
        <li v-if="!session.phases.length" class="next"><span>No phases in this case.</span></li>
      </ol>
      <button class="side-btn" :disabled="sending || session.finished" @click="act('feedback')">
        <i class="ti ti-message-check"></i>Request feedback</button>
      <button class="side-btn" :disabled="sending" @click="start(true)">
        <i class="ti ti-refresh"></i>[[ isTry ? 'Restart run' : 'Start over' ]]</button>
      <template v-if="isTry">
        <span class="eyebrow" style="margin-top:14px">Students</span>
        <button v-if="published" class="side-btn" @click="copyStudentLink(caseId)"><i class="ti ti-link"></i>Copy student link</button>
        <span v-else class="side-note">Publish the case to get a link students can open. They play the published version.</span>
      </template>
    </aside>
  </div>`,
};


function ssGet(key) { try { return sessionStorage.getItem(key); } catch { return null; } }
function ssSet(key, value) { try { sessionStorage.setItem(key, value); } catch { /* blocked */ } }
function ssDel(key) { try { sessionStorage.removeItem(key); } catch { /* blocked */ } }

const App = {
  components: { Topbar, UserMenu, GalleryView, EditorView, PlayerView },
  setup() {
    const gbtn = ref(null);

    async function boot() {
      try {
        let { user, error } = await initAuth({ app: 'vp' });
        if (!user) {
          // Google's callback returns to /vp/; come back to the share link after.
          if (playCaseId) ssSet(LS_AFTER_LOGIN, window.location.pathname);
          store.booting = false;
          await nextTick();
          ({ user, error } = await initAuth({ app: 'vp', buttonEl: gbtn.value }));
          store.authError = error;
          return;
        }
        const after = ssGet(LS_AFTER_LOGIN);
        if (after) {
          ssDel(LS_AFTER_LOGIN);
          if (!playCaseId && PLAY_PATH.test(after)) { window.location.replace(after); return; }
        }
        store.user = user;
        if (playCaseId) {
          try {
            store.playInfo = await api(`/vp/api/play/${playCaseId}/`);
          } catch (e) {
            store.playError = e.status === 404 ? 'This activity doesn’t exist or isn’t published yet.' : e.message;
          }
          return;
        }
        const content = await api('/vp/api/content/');
        store.pack = content;
        store.levels = content.levels;
        store.systemFields = content.system_fields;
        await refreshCases();
        const last = lsGet(LS_LAST_CASE);
        const target = store.cases.find(c => c.id === last) || store.cases[0];
        if (target) setCurrent(await api(`/vp/api/cases/${target.id}/`));
        else store.view = 'gallery';
      } catch (e) {
        if (e instanceof AuthError) { location.reload(); return; }
        store.authError = `Could not start VP Studio: ${e.message}`;
      } finally {
        store.booting = false;
      }
    }

    function onMouseDown(e) {
      if (e.target.closest('[data-pop]')) return;
      if (store.ui.pop?.type === 'fields') { store.ui.stepMenu = null; store.ui.userMenu = false; return; }
      closePops();
    }
    function onKey(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        if (dirty.value) save();
      } else if (e.key === 'Escape') {
        closePops();
        store.ui.assist = null;
      }
    }
    function onUnload(e) {
      if (dirty.value) { e.preventDefault(); e.returnValue = ''; }
    }
    function onResize() { store.vw = window.innerWidth; }

    onMounted(() => {
      document.addEventListener('mousedown', onMouseDown);
      window.addEventListener('keydown', onKey);
      window.addEventListener('beforeunload', onUnload);
      window.addEventListener('resize', onResize);
      boot();
    });
    onBeforeUnmount(() => {
      document.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('beforeunload', onUnload);
      window.removeEventListener('resize', onResize);
    });
    // A newly opened step closes any popovers left over from another one.
    watch(() => store.ui.openStep, () => { store.ui.pop = null; store.ui.assist = null; });

    return { store, gbtn, playCaseId };
  },
  template: `
  <div v-if="store.user && playCaseId" class="shell">
    <header class="topbar">
      <a class="logo" href="/vp/"><span class="logo-tile">vp</span><span class="logo-text">vp-studio</span></a>
      <span class="file-name">[[ store.playInfo?.title ]]</span>
      <div class="spacer"></div>
      <a v-if="store.playInfo?.is_owner" class="btn-ghost" href="/vp/" style="text-decoration:none"><i class="ti ti-pencil"></i><span>Edit</span></a>
      <UserMenu />
    </header>
    <main class="main">
      <PlayerView v-if="store.playInfo?.published" mode="play" :case-id="playCaseId" />
      <div v-else-if="store.playInfo || store.playError" class="stub">
        <span class="tile c-state"><i class="ti ti-lock"></i></span>
        <h2>Not available</h2>
        <p>[[ store.playError || 'This activity isn’t published yet. Publish it in the editor first.' ]]</p>
      </div>
    </main>
  </div>
  <div v-else-if="store.user && store.pack" class="shell">
    <Topbar />
    <main class="main">
      <template v-if="store.mode === 'player'">
        <PlayerView v-if="store.doc" :key="store.current.id" mode="try" :case-id="store.current.id" />
        <div v-else class="stub"><span class="tile c-accent"><i class="ti ti-player-play"></i></span>
          <h2>No case open</h2><p>Open or create a case, then try it here as a student would.</p>
          <button class="btn-ghost" @click="store.mode = 'author'"><i class="ti ti-arrow-left"></i>Back to the editor</button></div>
      </template>
      <GalleryView v-else-if="store.view === 'gallery' || !store.doc" />
      <EditorView v-else />
    </main>
  </div>
  <div v-else-if="store.booting" class="loading">Loading VP Studio…</div>
  <div v-else class="signin">
    <h1>VP Studio</h1>
    <p>Sign in with a pre-authorized Google account.</p>
    <div ref="gbtn"></div>
    <p class="error" v-if="store.authError">[[ store.authError ]]</p>
    <p><a href="/">Mundorum home</a></p>
  </div>

  <div class="backdrop" v-if="store.dialog" @mousedown.self="store.dialog = null">
    <div class="dialog" role="dialog" aria-modal="true">
      <div class="dialog-head"><b>[[ store.dialog.title ]]</b>
        <button class="icon-btn" title="Close" @click="store.dialog = null"><i class="ti ti-x"></i></button></div>
      <div class="dialog-body">
        <p v-if="store.dialog.intro" style="margin:0">[[ store.dialog.intro ]]</p>
        <ul v-if="store.dialog.items"><li v-for="(it, i) in store.dialog.items" :key="i">[[ it ]]</li></ul>
      </div>
      <div class="dialog-foot">
        <button v-for="a in store.dialog.actions" :key="a.label" :class="a.primary ? 'btn-primary' : 'btn-ghost'" @click="a.run">[[ a.label ]]</button>
      </div>
    </div>
  </div>
  <div class="toast" v-if="store.toast" :class="store.toast.kind" role="status">
    <span>[[ store.toast.text ]]</span>
    <button v-if="store.toast.action" @click="store.toast.action">[[ store.toast.actionLabel ]]</button>
  </div>`,
};

const app = createApp(App);
app.config.compilerOptions.delimiters = ['[[', ']]'];
app.mount('#app');
