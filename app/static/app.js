'use strict';

const el = (selector, root = document) => root.querySelector(selector);
const els = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const STEP_KEYS = ['region', 'venue', 'movie', 'dates', 'format', 'review'];
const STEP_LABELS = {
  region: 'Location',
  venue: 'Cinema',
  movie: 'Movie',
  dates: 'Dates',
  format: 'Format',
  review: 'Notify',
};
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const state = {
  view: 'dashboard',
  meta: null,
  watches: [],
  settings: null,
  wizard: null,
};

let toastTimer = null;

function esc(value) {
  return String(value === null || value === undefined ? '' : value).replace(
    /[&<>"']/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])
  );
}

function showToast(message, kind = 'ok') {
  const toast = el('#toast');
  toast.textContent = message;
  toast.className = 'toast' + (kind === 'error' ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add('hidden'), 3400);
}

async function api(path, options = {}) {
  const opts = { credentials: 'same-origin', ...options };
  if (opts.body && !opts.headers) {
    opts.headers = { 'Content-Type': 'application/json' };
  }
  const res = await fetch(path, opts);
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('unauthorized');
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data && data.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch (err) {
      /* not JSON */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// -- formatting ---------------------------------------------------------
function toDateInput(code) {
  if (!code || !/^\d{8}$/.test(code)) return '';
  return `${code.slice(0, 4)}-${code.slice(4, 6)}-${code.slice(6, 8)}`;
}

function fromDateInput(value) {
  return value ? value.replace(/-/g, '') : '';
}

function fmtDate(code) {
  if (!code || !/^\d{8}$/.test(code)) return '';
  const month = parseInt(code.slice(4, 6), 10);
  const day = parseInt(code.slice(6, 8), 10);
  return `${day} ${MONTHS[month - 1] || ''}`.trim();
}

function fmtInterval(seconds) {
  const value = parseInt(seconds, 10) || 60;
  if (value < 60) return `${value}s`;
  if (value % 60 === 0) return `${value / 60}m`;
  return `${value}s`;
}

function timeAgo(iso) {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'never';
  const diff = Math.max(0, (Date.now() - then) / 1000);
  if (diff < 60) return `${Math.max(1, Math.round(diff))}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

function describeWatchDates(watch) {
  if (watch.date_mode === 'today') return 'Today';
  if (watch.date_mode === 'tomorrow') return 'Tomorrow';
  if (watch.date_mode === 'exact') return fmtDate(watch.date_start) || 'One date';
  const start = watch.date_start ? fmtDate(watch.date_start) : 'Today';
  const end = watch.date_end ? fmtDate(watch.date_end) : '+7 days';
  return `${start} → ${end}`;
}

// -- dashboard ----------------------------------------------------------
async function refreshWatches() {
  try {
    state.watches = await api('/api/watches');
    renderDashboard();
  } catch (err) {
    if (err.message !== 'unauthorized') showToast(err.message, 'error');
  }
}

function renderDashboard() {
  const list = el('#watchList');
  const empty = el('#emptyState');
  list.innerHTML = '';
  empty.classList.toggle('hidden', state.watches.length > 0);
  state.watches.forEach((watch) => list.appendChild(renderWatchCard(watch)));
}

function renderWatchCard(watch) {
  const card = document.createElement('article');
  card.className = 'card';
  const status = watch.state || (watch.enabled ? 'watching' : 'paused');
  const matched = watch.matched_detail;
  const formats = watch.formats && watch.formats.length ? watch.formats.join(', ') : 'Any format';

  card.innerHTML = `
    <div class="card-head">
      <div>
        <div class="card-title">${esc(watch.movie_title)}</div>
        <div class="card-meta">${esc(watch.region_code)} · ${esc(watch.venue_name || watch.venue_code)}</div>
      </div>
      <span class="badge ${esc(status)}">${esc(status)}</span>
    </div>
    <div class="card-meta" style="margin-top:.35rem">
      ${esc(describeWatchDates(watch))} · ${esc(formats)} · every ${esc(fmtInterval(watch.interval_seconds))}
    </div>
    <div class="card-meta" style="margin-top:.2rem">last checked ${esc(timeAgo(watch.last_checked_at))}</div>
    ${watch.last_error ? `<p class="small error" style="margin-top:.4rem">${esc(watch.last_error)}</p>` : ''}
    ${
      matched
        ? `<div class="found-box">
             <div><strong>${esc(matched.date_display || '')}</strong> · ${esc(matched.showtime || '')}${
                 matched.format ? ' · ' + esc(matched.format) : ''
               }${matched.price ? ' · ' + esc(matched.price) : ''}</div>
             ${matched.url ? `<a href="${esc(matched.url)}" target="_blank" rel="noopener">Open in BookMyShow →</a>` : ''}
             ${matched.matches && matched.matches.length > 1 ? `<div class="small muted">${matched.matches.length} showtimes found</div>` : ''}
           </div>`
        : ''
    }
    <div class="actions">
      <button data-action="check">Check now</button>
      <button data-action="toggle">${watch.enabled ? 'Pause' : 'Resume'}</button>
      <button data-action="edit">Edit</button>
      <button data-action="delete" class="danger">Delete</button>
    </div>
  `;

  el('[data-action="check"]', card).addEventListener('click', () => checkNow(watch.id));
  el('[data-action="toggle"]', card).addEventListener('click', () => toggleWatch(watch));
  el('[data-action="edit"]', card).addEventListener('click', () => editWatch(watch));
  el('[data-action="delete"]', card).addEventListener('click', () => deleteWatch(watch));
  return card;
}

async function checkNow(watchId) {
  try {
    const result = await api(`/api/watches/${watchId}/check`, { method: 'POST' });
    if (result.matches && result.matches.length) {
      showToast(`Found ${result.matches.length} showtime(s)!`);
    } else if (result.error) {
      showToast(result.error, 'error');
    } else {
      showToast('No tickets yet — still watching');
    }
    await refreshWatches();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function toggleWatch(watch) {
  try {
    await api(`/api/watches/${watch.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !watch.enabled }),
    });
    await refreshWatches();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteWatch(watch) {
  if (!window.confirm(`Delete the watch for "${watch.movie_title}"?`)) return;
  try {
    await api(`/api/watches/${watch.id}`, { method: 'DELETE' });
    showToast('Watch deleted');
    await refreshWatches();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// -- wizard -------------------------------------------------------------
function startNewWizard() {
  state.wizard = {
    step: 0,
    editId: null,
    city: null,
    venue: null,
    movie: null,
    movies: null,
    formats: [],
    dateMode: 'range',
    dateStart: '',
    dateEnd: '',
    interval: 60,
    device: (state.settings && state.settings.pushbullet_device) || '',
  };
}

function editWatch(watch) {
  state.wizard = {
    step: 0,
    editId: watch.id,
    city: {
      code: watch.region_code,
      name: watch.region_code,
      slug: watch.region_slug,
      lat: watch.lat,
      lon: watch.lon,
    },
    venue: { code: watch.venue_code, name: watch.venue_name || watch.venue_code },
    movie: {
      title: watch.movie_title,
      event_code: watch.movie_event_code || null,
      free: !watch.movie_event_code,
    },
    movies: null,
    formats: [...(watch.formats || [])],
    dateMode: watch.date_mode || 'range',
    dateStart: watch.date_start || '',
    dateEnd: watch.date_end || '',
    interval: watch.interval_seconds || 60,
    device: watch.pushbullet_device || '',
  };
  setView('wizard');
}

function canContinue() {
  const w = state.wizard;
  switch (STEP_KEYS[w.step]) {
    case 'region':
      return !!w.city;
    case 'venue':
      return !!w.venue;
    case 'movie':
      return !!(w.movie && w.movie.title);
    case 'dates':
      return validDates();
    case 'format':
      return true;
    case 'review':
      return true;
    default:
      return false;
  }
}

function validDates() {
  const w = state.wizard;
  if (w.dateMode === 'exact') return !!w.dateStart;
  if (w.dateMode === 'range' && w.dateStart && w.dateEnd) return w.dateEnd >= w.dateStart;
  return true;
}

function advance() {
  if (!canContinue()) return;
  if (state.wizard.step < STEP_KEYS.length - 1) {
    state.wizard.step += 1;
    renderWizard();
  }
}

function goBack() {
  if (state.wizard.step > 0) {
    state.wizard.step -= 1;
    renderWizard();
  }
}

function renderWizard() {
  const w = state.wizard;
  el('#wizardTitle').textContent = w.editId ? 'Edit watch' : 'New watch';
  el('#steps').innerHTML = STEP_KEYS.map((key, index) => {
    const cls = index === w.step ? 'active' : index < w.step ? 'done' : '';
    return `<li class="${cls}"><span>${index + 1}</span>${STEP_LABELS[key]}</li>`;
  }).join('');

  el('#wizardBody').innerHTML = '';
  const renderers = {
    region: stepRegion,
    venue: stepVenue,
    movie: stepMovie,
    dates: stepDates,
    format: stepFormat,
    review: stepReview,
  };
  renderers[STEP_KEYS[w.step]]();
  renderNav();
}

function renderNav() {
  const w = state.wizard;
  const nav = el('#wizardNav');
  const parts = [];
  if (w.step > 0) parts.push('<button class="ghost" id="backBtn">Back</button>');
  if (w.step < STEP_KEYS.length - 1) {
    parts.push(
      `<button class="primary" id="nextBtn" ${canContinue() ? '' : 'disabled'}>Continue</button>`
    );
  } else {
    parts.push(
      `<button class="primary" id="saveBtn">${w.editId ? 'Save changes' : 'Start watching'}</button>`
    );
  }
  nav.innerHTML = parts.join('');
  const back = el('#backBtn');
  if (back) back.addEventListener('click', goBack);
  const next = el('#nextBtn');
  if (next) next.addEventListener('click', advance);
  const save = el('#saveBtn');
  if (save) save.addEventListener('click', saveWatch);
}

function updateNav() {
  renderNav();
}

// step 1: location
function stepRegion() {
  const w = state.wizard;
  const body = el('#wizardBody');
  body.innerHTML = `
    <label class="field">City or region
      <input id="citySearch" autocomplete="off" placeholder="e.g. Bengaluru, bang, BANG"
             value="${esc(w.city ? w.city.name : '')}">
    </label>
    ${w.city ? `<p class="small">Selected: <strong>${esc(w.city.name)}</strong> (${esc(w.city.code)})</p>` : ''}
    <div id="cityResults" class="results"></div>
  `;
  const input = el('#citySearch');
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const query = input.value.trim();
    if (!query) {
      el('#cityResults').innerHTML = '';
      return;
    }
    timer = setTimeout(() => searchCities(query), 250);
  });
  if (w.city) searchCities(w.city.name);
  else input.focus();
}

async function searchCities(query) {
  const box = el('#cityResults');
  if (!box) return;
  try {
    const cities = await api(`/api/regions?q=${encodeURIComponent(query)}`);
    if (!cities.length) {
      box.innerHTML = '<p class="muted small">No matches</p>';
      return;
    }
    box.innerHTML = cities
      .map(
        (city) => `
        <button class="result" data-code="${esc(city.code)}">
          <span class="result-title">${esc(city.name)}</span>
          <span class="result-meta">${esc(city.code)}${
            city.aliases && city.aliases.length ? ' · ' + esc(city.aliases.slice(0, 3).join(', ')) : ''
          }</span>
        </button>`
      )
      .join('');
    els('button', box).forEach((btn) => {
      btn.addEventListener('click', () => {
        const city = cities.find((item) => item.code === btn.dataset.code);
        const w = state.wizard;
        w.city = city;
        w.venue = null;
        w.movies = null;
        w.movie = null;
        renderWizard();
        advance();
      });
    });
  } catch (err) {
    box.innerHTML = `<p class="error small">${esc(err.message)}</p>`;
  }
}

// step 2: cinema
function stepVenue() {
  const w = state.wizard;
  const body = el('#wizardBody');
  if (!w.city) {
    body.innerHTML = '<p class="muted">Pick a location first.</p>';
    return;
  }
  body.innerHTML = `
    <p class="small muted">Cinemas in <strong>${esc(w.city.name)}</strong></p>
    <label class="field">Search cinemas
      <input id="venueSearch" autocomplete="off" placeholder="e.g. PVR, Orion, INOX">
    </label>
    <div id="venueResults" class="results"><p class="muted small">Loading…</p></div>
  `;
  const input = el('#venueSearch');
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => searchVenues(input.value.trim()), 250);
  });
  searchVenues('');
  input.focus();
}

async function searchVenues(query) {
  const w = state.wizard;
  const box = el('#venueResults');
  if (!box || !w.city) return;
  try {
    const venues = await api(
      `/api/venues?region=${encodeURIComponent(w.city.code)}&q=${encodeURIComponent(query)}`
    );
    if (!venues.length) {
      box.innerHTML = '<p class="muted small">No cinemas found</p>';
      return;
    }
    box.innerHTML = venues
      .map(
        (venue) => `
        <button class="result ${w.venue && w.venue.code === venue.code ? 'selected' : ''}" data-code="${esc(venue.code)}">
          <span class="result-title">${esc(venue.name)}</span>
          <span class="result-meta">${esc(venue.code)}${venue.address ? ' · ' + esc(venue.address) : ''}</span>
        </button>`
      )
      .join('');
    els('button', box).forEach((btn) => {
      btn.addEventListener('click', () => {
        const venue = venues.find((item) => item.code === btn.dataset.code);
        w.venue = venue;
        renderWizard();
        advance();
      });
    });
  } catch (err) {
    box.innerHTML = `<p class="error small">${esc(err.message)}</p>`;
  }
}

// step 3: movie
function stepMovie() {
  const w = state.wizard;
  const body = el('#wizardBody');
  if (!w.city) {
    body.innerHTML = '<p class="muted">Pick a location first.</p>';
    return;
  }
  body.innerHTML = `
    <label class="field">Search now-showing movies
      <input id="movieSearch" autocomplete="off" placeholder="Type a title…">
    </label>
    <div id="movieResults" class="results"><p class="muted small">Loading…</p></div>
    <p class="small muted" style="margin-top:1rem">Upcoming release not listed yet? Enter the title exactly as it appears on BookMyShow.</p>
    <div class="row">
      <input id="freeTitle" placeholder="Movie title" style="flex:1"
             value="${esc(w.movie && w.movie.free ? w.movie.title : '')}">
      <button id="useFreeTitle">Use this title</button>
    </div>
  `;
  const input = el('#movieSearch');
  input.addEventListener('input', () => renderMovieResults(input.value));
  el('#useFreeTitle').addEventListener('click', () => {
    const title = el('#freeTitle').value.trim();
    if (!title) {
      showToast('Enter a movie title', 'error');
      return;
    }
    w.movie = { title, event_code: null, free: true };
    advance();
  });
  loadMovies();
}

async function loadMovies() {
  const w = state.wizard;
  if (!w.city) return;
  try {
    if (!w.movies) {
      w.movies = await api(`/api/movies?region=${encodeURIComponent(w.city.code)}`);
    }
    renderMovieResults('');
  } catch (err) {
    const box = el('#movieResults');
    if (box) box.innerHTML = `<p class="error small">${esc(err.message)}</p>`;
  }
}

function renderMovieResults(filter) {
  const w = state.wizard;
  const box = el('#movieResults');
  if (!box) return;
  const needle = (filter || '').trim().toLowerCase();
  const movies = (w.movies || []).filter(
    (movie) => !needle || movie.title.toLowerCase().includes(needle)
  );
  if (!movies.length) {
    box.innerHTML = '<p class="muted small">No matching movies in this region.</p>';
    return;
  }
  box.innerHTML = movies
    .map(
      (movie) => `
      <button class="result ${
        w.movie && w.movie.event_code === movie.event_code ? 'selected' : ''
      }" data-code="${esc(movie.event_code)}">
        <span class="result-title">${esc(movie.title)}</span>
        <span class="result-meta">${esc([movie.language, movie.genre].filter(Boolean).join(' · '))}</span>
      </button>`
    )
    .join('');
  els('button', box).forEach((btn) => {
    btn.addEventListener('click', () => {
      const movie = movies.find((item) => item.event_code === btn.dataset.code);
      w.movie = { title: movie.title, event_code: movie.event_code, free: false };
      renderWizard();
      advance();
    });
  });
}

// step 4: dates
function stepDates() {
  const w = state.wizard;
  const modes = [
    ['today', 'Today'],
    ['tomorrow', 'Tomorrow'],
    ['exact', 'A specific date'],
    ['range', 'A date range'],
  ];
  el('#wizardBody').innerHTML = `
    <div class="chips" id="dateModes">
      ${modes
        .map(
          ([value, label]) =>
            `<button class="chip ${w.dateMode === value ? 'on' : ''}" data-mode="${value}">${label}</button>`
        )
        .join('')}
    </div>
    <div id="dateFields" style="margin-top:1rem"></div>
    <p class="small muted">For an unreleased movie, use a range starting on its release date.</p>
  `;
  els('#dateModes .chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      w.dateMode = chip.dataset.mode;
      renderWizard();
    });
  });
  renderDateFields();
}

function renderDateFields() {
  const w = state.wizard;
  const box = el('#dateFields');
  if (!box) return;
  if (w.dateMode === 'today' || w.dateMode === 'tomorrow') {
    box.innerHTML = `<p class="small muted">This watch checks ${w.dateMode} only.</p>`;
    return;
  }
  if (w.dateMode === 'exact') {
    box.innerHTML = `
      <label class="field">Show date
        <input type="date" id="dateStart" value="${toDateInput(w.dateStart)}">
      </label>`;
    el('#dateStart').addEventListener('change', (event) => {
      w.dateStart = fromDateInput(event.target.value);
      updateNav();
    });
    return;
  }
  box.innerHTML = `
    <div class="row">
      <label class="field" style="flex:1">From
        <input type="date" id="dateStart" value="${toDateInput(w.dateStart)}">
      </label>
      <label class="field" style="flex:1">To
        <input type="date" id="dateEnd" value="${toDateInput(w.dateEnd)}">
      </label>
    </div>
    <p class="small muted">Leave blank to start today and roll forward 7 days.</p>
  `;
  el('#dateStart').addEventListener('change', (event) => {
    w.dateStart = fromDateInput(event.target.value);
    updateNav();
  });
  el('#dateEnd').addEventListener('change', (event) => {
    w.dateEnd = fromDateInput(event.target.value);
    updateNav();
  });
}

// step 5: format
function stepFormat() {
  const w = state.wizard;
  const formats = (state.meta && state.meta.formats) || [];
  el('#wizardBody').innerHTML = `
    <p class="small muted">Leave empty to accept any format.</p>
    <div class="chips" id="formatChips">
      <button class="chip ${w.formats.length === 0 ? 'on' : ''}" data-format="">Any</button>
      ${formats
        .map(
          (format) =>
            `<button class="chip ${w.formats.includes(format) ? 'on' : ''}" data-format="${esc(format)}">${esc(format)}</button>`
        )
        .join('')}
    </div>
  `;
  els('#formatChips .chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const value = chip.dataset.format;
      if (!value) {
        w.formats = [];
      } else if (w.formats.includes(value)) {
        w.formats = w.formats.filter((item) => item !== value);
      } else {
        w.formats = [...w.formats, value];
      }
      renderWizard();
    });
  });
}

// step 6: review
function stepReview() {
  const w = state.wizard;
  const intervals = [
    [30, '30 seconds'],
    [60, '1 minute'],
    [120, '2 minutes'],
    [300, '5 minutes'],
  ];
  const tokenMissing = state.settings && !state.settings.token_configured;
  el('#wizardBody').innerHTML = `
    <div class="summary">
      <div><span>Movie</span><span>${esc(w.movie.title)}</span></div>
      <div><span>Cinema</span><span>${esc(w.venue.name)}</span></div>
      <div><span>Location</span><span>${esc(w.city.name)} (${esc(w.city.code)})</span></div>
      <div><span>Dates</span><span>${esc(describeWizardDates())}</span></div>
      <div><span>Format</span><span>${esc(w.formats.length ? w.formats.join(', ') : 'Any')}</span></div>
    </div>
    <label class="field">Check every
      <select id="interval">
        ${intervals
          .map(
            ([value, label]) =>
              `<option value="${value}" ${w.interval === value ? 'selected' : ''}>${label}</option>`
          )
          .join('')}
      </select>
    </label>
    <label class="field">Pushbullet device iden (optional)
      <input id="device" value="${esc(w.device || '')}" placeholder="Leave blank to notify all devices">
    </label>
    <div class="row">
      <button class="ghost" id="testPush">Send test notification</button>
    </div>
    ${
      tokenMissing
        ? '<p class="small error" style="margin-top:.6rem">Pushbullet is not configured yet — add a token in Settings.</p>'
        : ''
    }
  `;
  el('#interval').addEventListener('change', (event) => {
    w.interval = parseInt(event.target.value, 10) || 60;
  });
  el('#device').addEventListener('input', (event) => {
    w.device = event.target.value.trim();
  });
  el('#testPush').addEventListener('click', testPush);
}

function describeWizardDates() {
  const w = state.wizard;
  if (w.dateMode === 'today') return 'Today';
  if (w.dateMode === 'tomorrow') return 'Tomorrow';
  if (w.dateMode === 'exact') return w.dateStart ? fmtDate(w.dateStart) : 'Pick a date';
  const start = w.dateStart ? fmtDate(w.dateStart) : 'Today';
  const end = w.dateEnd ? fmtDate(w.dateEnd) : '+7 days';
  return `${start} → ${end}`;
}

async function saveWatch() {
  const w = state.wizard;
  if (!canContinue()) return;
  const payload = {
    region_code: w.city.code,
    region_slug: w.city.slug || null,
    lat: w.city.lat || null,
    lon: w.city.lon || null,
    venue_code: w.venue.code,
    venue_name: w.venue.name || null,
    movie_title: w.movie.title,
    movie_event_code: w.movie.event_code || null,
    formats: w.formats,
    date_mode: w.dateMode,
    date_start: w.dateMode === 'exact' || w.dateMode === 'range' ? w.dateStart || null : null,
    date_end: w.dateMode === 'range' ? w.dateEnd || null : null,
    interval_seconds: w.interval,
    pushbullet_device: w.device || null,
  };
  try {
    if (w.editId) {
      await api(`/api/watches/${w.editId}`, { method: 'PATCH', body: JSON.stringify(payload) });
      showToast('Watch updated');
    } else {
      await api('/api/watches', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Watch created — we will ping you when tickets appear');
    }
    startNewWizard();
    await refreshWatches();
    setView('dashboard');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function testPush() {
  try {
    await api('/api/notifications/test', { method: 'POST' });
    showToast('Test notification sent');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// -- settings -----------------------------------------------------------
async function renderSettings() {
  const section = el('#view-settings');
  try {
    state.settings = await api('/api/settings');
  } catch (err) {
    section.innerHTML = `<h1>Settings</h1><p class="error">${esc(err.message)}</p>`;
    return;
  }
  const s = state.settings;
  section.innerHTML = `
    <h1>Settings</h1>
    <div class="card">
      <h2>Pushbullet</h2>
      <p class="small muted">Create a token at pushbullet.com → Settings → Access Tokens.</p>
      <p style="margin:.6rem 0">
        ${
          s.token_configured
            ? `<span class="badge found">configured</span> <span class="small muted">${esc(s.token_hint || '')}${
                s.token_source ? ` (from ${esc(s.token_source)})` : ''
              }</span>`
            : '<span class="badge error">not configured</span>'
        }
      </p>
      <label class="field">Access token
        <input id="pbToken" type="password" autocomplete="off"
               placeholder="${s.token_configured ? 'Replace existing token' : 'Paste token'}">
      </label>
      <label class="field">Device iden (optional)
        <input id="pbDevice" value="${esc(s.pushbullet_device || '')}" placeholder="Leave blank to notify all devices">
      </label>
      <div class="row">
        <button class="primary" id="saveSettings">Save</button>
        <button class="ghost" id="settingsTestPush">Send test</button>
      </div>
      ${
        s.token_source === 'env'
          ? '<p class="small muted" style="margin-top:.6rem">The token comes from the <code>PUSHBULLET_TOKEN</code> environment variable and overrides anything saved here.</p>'
          : ''
      }
    </div>
    <div class="card" style="margin-top:.8rem">
      <h2>Session</h2>
      <p class="small muted">${
        s.auth_enabled
          ? 'This instance is protected by an access token.'
          : 'Access token is disabled (APP_TOKEN is empty).'
      }</p>
      <div class="row" style="margin-top:.6rem">
        <button class="ghost" id="logoutBtn">Log out</button>
      </div>
    </div>
  `;
  el('#saveSettings').addEventListener('click', async () => {
    try {
      const token = el('#pbToken').value.trim();
      const body = { pushbullet_device: el('#pbDevice').value };
      if (token) body.pushbullet_token = token;
      state.settings = await api('/api/settings', { method: 'PATCH', body: JSON.stringify(body) });
      showToast('Settings saved');
      renderSettings();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
  el('#settingsTestPush').addEventListener('click', testPush);
  const logout = el('#logoutBtn');
  if (logout) {
    logout.addEventListener('click', async () => {
      try {
        await api('/api/logout', { method: 'POST' });
      } catch (err) {
        /* ignore */
      }
      window.location.href = '/login';
    });
  }
}

// -- navigation ---------------------------------------------------------
function setView(name) {
  state.view = name;
  els('.view').forEach((view) => view.classList.add('hidden'));
  const view = el(`#view-${name}`);
  if (view) view.classList.remove('hidden');
  els('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.view === name));
  if (name === 'wizard') renderWizard();
  if (name === 'settings') renderSettings();
  if (name === 'dashboard') renderDashboard();
}

function bindNav() {
  els('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      if (tab.dataset.view === 'wizard') startNewWizard();
      setView(tab.dataset.view);
    });
  });
  el('#newWatchBtn').addEventListener('click', () => {
    startNewWizard();
    setView('wizard');
  });
  el('#cancelWizard').addEventListener('click', () => {
    startNewWizard();
    setView('dashboard');
  });
}

async function init() {
  try {
    state.meta = await api('/api/meta');
  } catch (err) {
    /* meta is only used for the format chips */
  }
  try {
    state.settings = await api('/api/settings');
  } catch (err) {
    /* settings view will surface the error */
  }
  startNewWizard();
  bindNav();
  await refreshWatches();
  setView('dashboard');
  setInterval(() => {
    if (state.view === 'dashboard' && !document.hidden) refreshWatches();
  }, 10000);
}

init();
