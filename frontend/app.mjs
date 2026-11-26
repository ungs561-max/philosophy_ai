const instances = new WeakMap();
export default function mount(component) {
  const root = component.parentElement.querySelector('.library');
  if (!root) return;
  if (!instances.has(root)) instances.set(root, initialize(root, component.data));
  instances.get(root)(component);
}

function initialize(root, initial) {
  const profiles = initial.profiles;
  const poses = ['idle', 'listening', 'thinking', 'speaking'];
  const $ = id => root.querySelector('#' + id);
  const nav = $('philosophers');
  const modes = $('modes');
  const mobileMode = $('mobile-mode');
  const draft = $('draft');
  const messages = $('messages');
  const scroll = $('panel-scroll');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const mobile = matchMedia('(max-width: 800px)');
  const art = (id, pose) => profiles[id].art[pose];
  const storageKey = 'philosophers-library-streamlit-v1';
  let stored;
  try { stored = JSON.parse(sessionStorage.getItem(storageKey)); } catch { /* Fresh browser session. */ }
  const user = stored?.user || crypto.randomUUID();
  const histories = stored?.histories || {};
  const drafts = {};
  let id = 'epictetus';
  let mode = 'counsel';
  let test = false;
  const config = initial.config;
  let bridge;
  let activeRequest;
  let running = false;
  let skipTyping = false;
  let portraitVersion = 0;
  const loaded = new Map();

  const sceneToggle = $('scene-toggle');
  const dailyToggle = $('daily-toggle');
  function collapseScene(collapsed) {
    root.classList.toggle('scene-collapsed', collapsed);
    sceneToggle.setAttribute('aria-expanded', String(!collapsed));
    sceneToggle.firstElementChild.textContent = collapsed ? '일러스트 펼치기' : '일러스트 접기';
  }
  sceneToggle.onclick = () => collapseScene(!root.classList.contains('scene-collapsed'));
  dailyToggle.onclick = () => dailyToggle.setAttribute('aria-expanded', String(dailyToggle.getAttribute('aria-expanded') !== 'true'));

  function resizeDraft() {
    draft.style.height = '';
    if (!mobile.matches) return;
    const border = draft.offsetHeight - draft.clientHeight;
    draft.style.height = `${draft.scrollHeight + border}px`;
  }

  let outerViewport;
  let frame;
  try {
    if (window.parent !== window) {
      outerViewport = window.parent.visualViewport;
      frame = window.frameElement;
      root.classList.toggle('cloud-frame', location.pathname.includes('/~/+/'));
    }
  } catch { /* A cross-origin frame can only measure its own viewport. */ }
  const viewportEvents = new AbortController();
  function syncViewport() {
    if (!root.isConnected) {
      viewportEvents.abort();
      return;
    }
    if (!mobile.matches) {
      root.style.removeProperty('--mobile-height');
      root.classList.remove('short-screen');
      resizeDraft();
      return;
    }
    const height = window.visualViewport?.height ?? window.innerHeight;
    const available = outerViewport && frame
      ? Math.min(height, outerViewport.height - Math.max(0, frame.getBoundingClientRect().top - outerViewport.offsetTop))
      : height;
    root.style.setProperty('--mobile-height', `${Math.floor(Math.max(0, available))}px`);
    root.classList.toggle('short-screen', available < 500);
    resizeDraft();
  }
  const options = { signal: viewportEvents.signal };
  window.addEventListener('resize', syncViewport, options);
  window.visualViewport?.addEventListener('resize', syncViewport, options);
  outerViewport?.addEventListener('resize', syncViewport, options);
  outerViewport?.addEventListener('scroll', syncViewport, options);

  function context() { return `${test ? 'test' : 'dify'}:${id}:${mode}`; }
  function history() { return histories[context()] ??= { messages: [], conversationId: '' }; }
  function persist() {
    try { sessionStorage.setItem(storageKey, JSON.stringify({ user, histories })); } catch { /* Continue in memory. */ }
  }
  function imageFor(key, pose) {
    const src = art(key, pose);
    if (!loaded.has(src)) {
      const image = new Image();
      image.alt = '';
      image.className = 'portrait';
      image.dataset.pose = `${key}-${pose}`;
      image.src = src;
      loaded.set(src, image);
    }
    return loaded.get(src);
  }
  async function showPose(pose) {
    const version = ++portraitVersion;
    const host = $('portraits');
    host.dataset.state = pose;
    const image = imageFor(id, pose);
    try { await image.decode(); } catch { return; }
    if (version !== portraitVersion) return;
    const previous = host.querySelector('.visible');
    if (previous === image) return;
    host.append(image);
    // The previous pose remains painted beneath the incoming image until the fade ends.
    image.getBoundingClientRect();
    image.classList.add('visible');
    if (previous) {
      previous.classList.remove('visible');
      setTimeout(() => {
        if (!previous.classList.contains('visible')) previous.remove();
      }, reducedMotion.matches ? 0 : 420);
    }
  }
  function preload(id) {
    for (const pose of poses) imageFor(id, pose);
  }

  function setAssistantText(body, text) {
    const lines = text.split('\n');
    body.replaceChildren();
    for (const [index, line] of lines.entries()) {
      if (index) body.append('\n');
      // Only style clearly delimited quotation lines; keep normal prose in Pretendard.
      const marked = /^\s*>\s+(.+)$/.exec(line);
      if (marked || /^\s*“[^”]+”\s*$/.test(line)) {
        const quote = document.createElement('span');
        quote.className = 'source-quote';
        quote.textContent = marked ? marked[1] : line;
        body.append(quote);
      } else {
        body.append(line);
      }
    }
  }

  function message(role, text, greeting = false) {
    const article = document.createElement('article');
    article.className = `message ${role}`;
    const label = document.createElement('span');
    label.className = 'speaker';
    label.textContent = role === 'user' ? '나' : profiles[id].name;
    if (test && role === 'assistant' && !greeting) label.textContent += ' · 테스트 응답';
    const body = document.createElement('p');
    if (role === 'assistant') setAssistantText(body, text);
    else body.textContent = text;
    article.append(label, body);
    messages.append(article);
    return body;
  }
  function bottom() { scroll.scrollTop = scroll.scrollHeight; }
  function nearBottom() { return scroll.scrollHeight - scroll.clientHeight - scroll.scrollTop <= 32; }
  function status(text) { $('status').textContent = text; }
  function setting() { return config?.profiles[id][mode]; }
  function available() { return Boolean(config && (test || setting()?.available)); }
  function controls() {
    for (const button of [...nav.children, ...modes.children, $('test-mode')]) button.disabled = running;
    mobileMode.disabled = running;
    $('mobile-reset').disabled = running;
    draft.disabled = running || !available();
    $('send').disabled = draft.disabled || !draft.value.trim();
    $('daily-action').disabled = draft.disabled;
    $('reset').disabled = running;
  }
  function render() {
    const profile = profiles[id];
    const canStudy = config.studyEnabled.includes(id);
    if (!canStudy) mode = 'counsel';
    modes.hidden = !canStudy;
    mobileMode.hidden = !canStudy;
    mobileMode.value = mode;
    const card = setting()?.card;
    const studying = mode === 'study';
    for (const button of nav.children) button.setAttribute('aria-pressed', String(button.dataset.id === id));
    for (const button of modes.children) button.setAttribute('aria-pressed', String(button.dataset.mode === mode));
    $('test-mode').setAttribute('aria-pressed', String(test));
    $('backdrop').src = art(id, 'background');
    $('name').textContent = profile.name;
    $('latin').textContent = `${profile.latin} · ${profile.school}`;
    $('intro').textContent = profile.intro;
    $('era').textContent = profile.era;
    $('place').textContent = profile.place;
    $('daily').hidden = !card;
    if (card) {
      $('daily-title').textContent = studying ? '오늘의 철학 개념' : '오늘의 명언';
      dailyToggle.textContent = studying ? '오늘의 철학 개념' : '오늘의 명언 · 성찰 질문';
      dailyToggle.setAttribute('aria-expanded', 'false');
      $('daily-main').textContent = studying ? card.term : `“${card.quote}”`;
      $('daily-main').classList.toggle('source-quote', !studying);
      $('daily-source').textContent = studying ? `${card.philosopher} · 개념 요약` : `— ${card.philosopher}`;
      $('daily-detail').textContent = studying ? card.explanation : `성찰 질문 · ${card.question}`;
      $('daily-action').textContent = studying ? '이 개념을 공부하기' : '이 질문으로 대화하기';
    }
    messages.replaceChildren();
    for (const entry of history().messages) message(entry.role, entry.content);
    const empty = !history().messages.length;
    scroll.classList.toggle('welcome', empty);
    if (empty) message('assistant', studying ? `${profile.school}에서 궁금한 개념을 함께 살펴봅시다.` : profile.greeting, true);
    scroll.scrollTop = 0;
    if (history().messages.length) bottom();
    draft.value = drafts[context()] || '';
    resizeDraft();
    draft.placeholder = studying ? '어떤 철학 개념이 궁금한가요?' : '요즘 어떤 고민이 있나요?';
    status(test ? '임시 응답 테스트 중 · 실제 AI 답변이 아닙니다'
      : config && !available() ? '연결 준비 중 · 테스트 모드에서 대화할 수 있습니다' : '');
    preload(id);
    showPose(draft.value ? 'listening' : 'idle');
    controls();
  }

  for (const [key, profile] of Object.entries(profiles)) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.id = key;
    button.textContent = profile.name;
    button.onclick = () => { id = key; render(); };
    nav.append(button);
  }
  for (const button of modes.children) button.onclick = () => { mode = button.dataset.mode; render(); };
  mobileMode.onchange = () => { mode = mobileMode.value; render(); };
  $('show-profile').onclick = () => {
    const profile = profiles[id];
    $('mobile-actions').open = false;
    $('profile-name').textContent = profile.name;
    $('profile-school').textContent = `${profile.latin} · ${profile.school}`;
    $('profile-intro').textContent = profile.intro;
    $('profile-details').showModal();
  };
  $('mobile-reset').onclick = () => {
    $('mobile-actions').open = false;
    $('reset').click();
  };
  $('test-mode').onclick = () => { test = !test; render(); };
  draft.addEventListener('focus', () => {
    if (mobile.matches) collapseScene(true);
  });
  draft.addEventListener('input', () => {
    drafts[context()] = draft.value;
    resizeDraft();
    showPose(draft.value ? 'listening' : 'idle');
    controls();
  });
  draft.addEventListener('keydown', event => {
    if (!mobile.matches && event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      $('form').requestSubmit();
    }
  });
  $('form').onsubmit = event => { event.preventDefault(); send(false); };
  $('daily-action').onclick = () => send(true);
  $('skip').onclick = () => { skipTyping = true; $('skip').hidden = true; };
  $('reset').onclick = () => {
    if (!history().messages.length || confirm('현재 철학자와 모드의 대화를 지우고 새로 시작할까요?')) {
      delete histories[context()];
      delete drafts[context()];
      persist();
      render();
    }
  };

  async function waitForDialogue(payload, output) {
    const requestId = crypto.randomUUID();
    const deadline = Date.now() + 140000;
    activeRequest = { requestId, snapshot: null };
    try {
      bridge.setTriggerValue('request', { ...payload, requestId });
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 220));
        if (!root.isConnected) throw new Error('대화 연결이 종료되었습니다.');
        const result = activeRequest.snapshot;
        if (result?.error) throw new Error(result.error);
        if (result?.answer && !payload.test) output(result.answer);
        if (result?.done) return result;
        bridge.setTriggerValue('poll', requestId);
      }
      throw new Error('답변을 기다리는 시간이 초과되었습니다.');
    } finally {
      activeRequest = null;
    }
  }

  async function send(fromCard) {
    const text = draft.value.trim();
    if (running || !available() || (!fromCard && !text)) return;
    if (fromCard && history().messages.length && !confirm('이 주제로 새 대화를 시작할까요?')) return;
    running = true;
    if (mobile.matches) collapseScene(true);
    skipTyping = false;
    const current = history();
    const card = setting().card;
    const display = fromCard
      ? mode === 'study'
        ? `오늘의 철학 개념 '${card.term}'을 공부하고 싶어요.`
        : `${card.philosopher}의 명언을 바탕으로 '${card.question}'에 대해 상담하고 싶어요.`
      : text;
    delete drafts[context()];
    draft.value = '';
    resizeDraft();
    controls();
    if (fromCard || !current.messages.length) messages.replaceChildren();
    scroll.classList.remove('welcome');
    const question = message('user', display);
    showPose('thinking');
    status(`${profiles[id].name} 님이 생각하고 있습니다…`);
    bottom();
    let answer = '';
    let reply;
    let conversationId = fromCard ? '' : current.conversationId;
    function output(value) {
      const follow = !mobile.matches || nearBottom();
      if (!reply) {
        reply = message('assistant', '');
        showPose('speaking');
        status(test ? '임시 테스트 응답을 표시하고 있습니다…' : '답변을 받고 있습니다…');
      }
      setAssistantText(reply, value);
      if (follow) bottom();
    }
    try {
      const result = await waitForDialogue({ id, mode, fromCard, text, user, conversationId, test }, output);
      answer = result.answer;
      if (typeof answer !== 'string' || !answer.trim()) throw new Error('답변이 비어 있습니다.');
      question.textContent = result.display ?? display;
      conversationId = result.conversationId || conversationId;
      if (test) {
        const characters = [...answer];
        if (!reducedMotion.matches) {
          $('skip').hidden = false;
          const step = Math.max(2, Math.ceil(characters.length / 60));
          for (let i = step; i < characters.length && !skipTyping; i += step) {
            output(characters.slice(0, i).join(''));
            await new Promise(resolve => setTimeout(resolve, 24));
          }
        }
      }
      output(answer);
      if (fromCard) current.messages = [];
      current.messages.push({ role: 'user', content: question.textContent }, { role: 'assistant', content: answer });
      current.conversationId = conversationId;
      persist();
      status(test ? '임시 응답 테스트 중 · 실제 AI 답변이 아닙니다' : '');
    } catch (error) {
      drafts[context()] = fromCard ? '' : text;
      render();
      status(error instanceof TypeError ? '연결 오류가 발생했습니다. 다시 시도해 주세요.' : error.message);
    } finally {
      running = false;
      $('skip').hidden = true;
      showPose('idle');
      controls();
    }
  }

  test = config.demo;
  render();
  syncViewport();
  const warmOtherScenes = () => {
    for (const key of Object.keys(profiles)) {
      if (key !== id) {
        imageFor(key, 'background');
        imageFor(key, 'idle');
      }
    }
  };
  if ('requestIdleCallback' in window) requestIdleCallback(warmOtherScenes, { timeout: 1200 });
  else setTimeout(warmOtherScenes, 500);

  return component => {
    bridge = component;
    const snapshot = component.data?.snapshot;
    if (activeRequest && snapshot?.requestId === activeRequest.requestId) activeRequest.snapshot = snapshot;
  };
}
