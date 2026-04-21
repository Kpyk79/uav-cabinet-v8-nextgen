/**
 * UAV Cabinet — Interactive Tutorial Engine
 * Підтримує покроковий тур з підсвіткою елементів та підказками.
 * Використання: UAVTutorial.start(steps) або UAVTutorial.startPage('index')
 */
(function (global) {
  'use strict';

  // ─── CSS ──────────────────────────────────────────────────────────────────
  const STYLE = `
    #uav-tutorial-overlay {
      position: fixed; inset: 0; z-index: 99990;
      pointer-events: none;
      transition: opacity 0.3s ease;
    }
    #uav-tutorial-overlay.active { pointer-events: none; }

    #uav-tutorial-backdrop {
      position: fixed; inset: 0; z-index: 99991;
      background: transparent;
      pointer-events: all;
      transition: opacity 0.3s ease;
    }

    #uav-tutorial-spotlight {
      position: fixed; z-index: 99992;
      border-radius: 14px;
      box-shadow:
        0 0 0 4px rgba(34, 197, 94, 0.6),
        0 0 0 9999px rgba(6, 11, 24, 0.85);
      transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
      pointer-events: none;
    }

    #uav-tutorial-tooltip {
      position: fixed; z-index: 99999;
      background: rgba(15, 23, 42, 0.97);
      border: 1px solid rgba(34, 197, 94, 0.35);
      border-radius: 18px;
      padding: 22px 24px 18px;
      max-width: 340px;
      min-width: 260px;
      box-shadow:
        0 8px 40px rgba(0,0,0,0.6),
        0 0 0 1px rgba(255,255,255,0.04),
        inset 0 1px 0 rgba(255,255,255,0.06);
      font-family: 'Inter', sans-serif;
      color: #e2e8f0;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      pointer-events: all;
    }

    #uav-tutorial-tooltip .tut-step-badge {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 10px; font-weight: 800; text-transform: uppercase;
      letter-spacing: 0.08em; color: #22c55e;
      background: rgba(34,197,94,0.1);
      border: 1px solid rgba(34,197,94,0.2);
      padding: 3px 10px; border-radius: 99px;
      margin-bottom: 12px;
    }

    #uav-tutorial-tooltip .tut-icon {
      font-size: 22px; margin-bottom: 8px; display: block;
    }

    #uav-tutorial-tooltip .tut-title {
      font-size: 15px; font-weight: 800; color: #f1f5f9;
      margin-bottom: 8px; line-height: 1.3;
    }

    #uav-tutorial-tooltip .tut-desc {
      font-size: 13px; color: #94a3b8; line-height: 1.6;
      margin-bottom: 18px;
    }

    #uav-tutorial-tooltip .tut-desc strong { color: #e2e8f0; font-weight: 700; }

    #uav-tutorial-tooltip .tut-footer {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
    }

    #uav-tutorial-tooltip .tut-progress {
      display: flex; gap: 5px; align-items: center;
    }

    #uav-tutorial-tooltip .tut-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: rgba(100,116,139,0.4);
      transition: all 0.25s ease;
    }
    #uav-tutorial-tooltip .tut-dot.active {
      background: #22c55e; width: 18px; border-radius: 3px;
    }
    #uav-tutorial-tooltip .tut-dot.done {
      background: rgba(34,197,94,0.4);
    }

    #uav-tutorial-tooltip .tut-btns {
      display: flex; gap: 8px; align-items: center;
    }

    #uav-tutorial-tooltip .tut-btn-skip {
      font-size: 11px; font-weight: 700; color: #475569;
      background: none; border: none; cursor: pointer;
      padding: 6px 8px; border-radius: 8px;
      transition: color 0.2s, background 0.2s;
      text-transform: uppercase; letter-spacing: 0.05em;
    }
    #uav-tutorial-tooltip .tut-btn-skip:hover { color: #94a3b8; background: rgba(255,255,255,0.05); }

    #uav-tutorial-tooltip .tut-btn-prev {
      font-size: 12px; font-weight: 700; color: #64748b;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      cursor: pointer; padding: 8px 14px; border-radius: 10px;
      transition: all 0.2s; text-transform: uppercase; letter-spacing: 0.04em;
    }
    #uav-tutorial-tooltip .tut-btn-prev:hover { color: #e2e8f0; background: rgba(255,255,255,0.1); }

    #uav-tutorial-tooltip .tut-btn-next {
      font-size: 12px; font-weight: 800; color: #fff;
      background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
      border: none; cursor: pointer;
      padding: 8px 18px; border-radius: 10px;
      transition: all 0.2s; text-transform: uppercase; letter-spacing: 0.04em;
      box-shadow: 0 3px 12px rgba(22,163,74,0.3);
    }
    #uav-tutorial-tooltip .tut-btn-next:hover {
      transform: translateY(-1px);
      box-shadow: 0 5px 18px rgba(22,163,74,0.4);
    }
    #uav-tutorial-tooltip .tut-btn-next:active { transform: translateY(0) scale(0.97); }

    #uav-tutorial-tooltip .tut-btn-next.finish {
      background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
      box-shadow: 0 3px 12px rgba(37,99,235,0.3);
    }
    #uav-tutorial-tooltip .tut-btn-next.finish:hover {
      box-shadow: 0 5px 18px rgba(37,99,235,0.4);
    }

    /* Help button */
    #uav-tutorial-help-btn {
      position: fixed;
      bottom: 20px; right: 20px;
      z-index: 9999;
      width: 46px; height: 46px;
      border-radius: 50%;
      background: linear-gradient(135deg, rgba(34,197,94,0.2) 0%, rgba(34,197,94,0.1) 100%);
      border: 1.5px solid rgba(34,197,94,0.45);
      color: #22c55e;
      font-size: 20px; font-weight: 900; line-height: 1;
      display: flex; align-items: center; justify-content: center;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(34,197,94,0.2), inset 0 1px 0 rgba(255,255,255,0.06);
      transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
      font-family: 'Inter', Georgia, sans-serif;
      user-select: none;
    }
    #uav-tutorial-help-btn:hover {
      background: rgba(34,197,94,0.25);
      box-shadow: 0 6px 28px rgba(34,197,94,0.25);
      transform: translateY(-2px) scale(1.05);
    }
    #uav-tutorial-help-btn:active { transform: scale(0.95); }

    /* Animate-in */
    @keyframes tutFadeIn {
      from { opacity: 0; transform: translateY(8px) scale(0.97); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }
    #uav-tutorial-tooltip { animation: tutFadeIn 0.3s ease forwards; }

    /* Arrow */
    #uav-tutorial-tooltip::before {
      content: '';
      position: absolute;
      width: 10px; height: 10px;
      background: rgba(15, 23, 42, 0.97);
      border: 1px solid rgba(34,197,94,0.35);
      transform: rotate(45deg);
    }
    #uav-tutorial-tooltip.arrow-bottom::before {
      bottom: -6px; left: 50%; margin-left: -5px;
      border-top: none; border-left: none;
    }
    #uav-tutorial-tooltip.arrow-top::before {
      top: -6px; left: 50%; margin-left: -5px;
      border-bottom: none; border-right: none;
    }
    #uav-tutorial-tooltip.arrow-right::before {
      right: -6px; top: 50%; margin-top: -5px;
      border-top: none; border-right: none; /* Corrected for right */
      border-left: none; border-bottom: none;
    }
    #uav-tutorial-tooltip.arrow-left::before {
      left: -6px; top: 50%; margin-top: -5px;
      border-bottom: none; border-left: none;
    }
    #uav-tutorial-tooltip.arrow-none::before { display: none; }
  `;

  // ─── Step definitions per page ────────────────────────────────────────────

  const PAGE_STEPS = {

    index: [
      {
        target: null,
        icon: '🚁',
        title: 'Ласкаво просимо до UAV Cabinet!',
        desc: 'Це <strong>система управління польотами БПЛА</strong>. Цей тур покаже як користуватись основними функціями. Натисніть <strong>Далі</strong> щоб почати.',
        position: 'center'
      },
      {
        target: '#loginScreen',
        icon: '🔐',
        title: 'Авторизація',
        desc: 'Виберіть свій <strong>підрозділ</strong>, введіть <strong>прізвище</strong> та <strong>пароль</strong>. Після входу відкриється робоча панель.',
        position: 'right'
      },
      {
        target: '#userBadge',
        icon: '👤',
        title: 'Ваш профіль',
        desc: 'Відображає ваш <strong>підрозділ і прізвище</strong>. Якщо відсутнє інтернет-з\'єднання — з\'явиться позначка <strong>OFFLINE</strong> і дані збережуться локально.',
        position: 'bottom'
      },
      {
        target: '.flex.flex-wrap.gap-1\\.5.justify-end',
        icon: '🧭',
        title: 'Навігаційна панель',
        desc: '<strong>7 кнопок</strong> швидкого доступу:<br>🟣 Заявка · 🔵 Журнал · 🟤 Звіти · 🟠 Аналітика · 🟢 Довідник · 🔵 Метео · 🔴 Вихід',
        position: 'bottom'
      },
      {
        target: '#flightForm',
        icon: '📋',
        title: 'Форма польоту',
        desc: 'Тут вводяться всі дані про один виліт. Заповніть поля <strong>зверху вниз</strong> — дата, зміна, БпЛА, маршрут, час, результат.',
        position: 'right'
      },
      {
        target: '#date',
        icon: '📅',
        title: 'Дата та час зміни',
        desc: 'Виберіть <strong>дату польоту</strong> та вкажіть <strong>початок і кінець зміни</strong> (наприклад 08:00 – 20:00).',
        position: 'bottom'
      },
      {
        target: '#drone',
        icon: '🚁',
        title: 'Вибір БпЛА',
        desc: 'Оберіть <strong>борт</strong> зі списку. Перелік завантажується з бази даних вашого підрозділу.',
        position: 'bottom'
      },
      {
        target: '#route',
        icon: '📍',
        title: 'Маршрут',
        desc: 'Введіть <strong>район або маршрут польоту</strong>. Це поле потрапляє в донесення та звіти.',
        position: 'bottom'
      },
      {
        target: '.grid.grid-cols-3.gap-3 .time-pill.takeoff',
        icon: '⏱️',
        title: 'Час: Зліт / Тривалість / Посадка',
        desc: 'Введіть час <strong>зльоту</strong> та <strong>тривалість</strong> у хвилинах — час посадки <strong>розрахується автоматично</strong>. Формат: ГГ:ХХ.',
        position: 'bottom'
      },
      {
        target: '#dist',
        icon: '📏',
        title: 'Дистанція, АКБ, Цикли',
        desc: 'Вкажіть <strong>дистанцію</strong> у метрах, <strong>номер акумулятора</strong> та кількість <strong>циклів заряду</strong>.',
        position: 'bottom'
      },
      {
        target: '#result',
        icon: '✅',
        title: 'Результат польоту',
        desc: 'Оберіть результат виконання завдання. Якщо обрати <strong>"Не виконано"</strong> — з\'явиться поле для коментаря з поясненням.',
        position: 'bottom'
      },
      {
        target: '#submitBtn',
        icon: '➕',
        title: 'Додати в чернетку',
        desc: 'Натисніть цю кнопку щоб <strong>зберегти виліт у чернетку</strong>. Можна додати кілька вильотів перед публікацією.',
        position: 'top'
      },
      {
        target: '#draftList',
        icon: '📝',
        title: 'Чернетка',
        desc: 'Тут відображаються всі додані вильоти. Можна <strong>редагувати або видаляти</strong> кожен запис перед відправкою.',
        position: 'left'
      },
      {
        target: '#cusBefore',
        icon: '📄',
        title: 'Зведення ЦУС',
        desc: 'Автоматично формуються два зведення: <strong>до 00:00</strong> (денна зміна) та <strong>після 00:00</strong> (нічна). Можна скопіювати текст кнопкою "Копіювати".',
        position: 'left'
      },
      {
        target: '#publishBtn',
        icon: '📡',
        title: 'Опублікувати донесення',
        desc: 'Коли всі вильоти додані — натисніть <strong>"Опублікувати"</strong>. Дані збережуться в журнал і сформується звіт.',
        position: 'top'
      },
      {
        target: null,
        icon: '🎉',
        title: 'Тур завершено!',
        desc: 'Ви ознайомились з основними функціями головної сторінки. Натисніть <strong>кнопку "?"</strong> в правому нижньому куті щоб переглянути тур знову.',
        position: 'center'
      }
    ],

    dashboard: [
      {
        target: null,
        icon: '📖',
        title: 'Журнал польотів',
        desc: 'Тут відображається <strong>повна історія вильотів</strong> вашого підрозділу, згрупована по змінах.',
        position: 'center'
      },
      {
        target: '#logsContainer',
        icon: '🗂️',
        title: 'Місії та вильоти',
        desc: 'Кожна картка — це <strong>одна зміна</strong>. Всередині перераховані окремі вильоти з часом, бортом, маршрутом та результатом.',
        position: 'center'
      },
      {
        target: null,
        icon: '📊',
        title: 'Експорт даних',
        desc: 'Кнопка <strong>"Експорт в Excel"</strong> вгорі дозволяє вивантажити журнал у таблицю для подальшої роботи.',
        position: 'center'
      },
      {
        target: null,
        icon: '✅',
        title: 'Готово!',
        desc: 'Ви ознайомились з журналом польотів. Повертайтесь на <strong>головну</strong> щоб продовжити роботу.',
        position: 'center'
      }
    ],

    report: [
      {
        target: null,
        icon: '📑',
        title: 'Генератор звітів',
        desc: 'На цій сторінці можна <strong>сформувати офіційний звіт</strong> за вибраний період у форматі .docx.',
        position: 'center'
      },
      {
        target: null,
        icon: '📅',
        title: 'Вибір періоду',
        desc: 'Оберіть <strong>дати початку і кінця</strong> потрібного звітного періоду.',
        position: 'center'
      },
      {
        target: null,
        icon: '⬇️',
        title: 'Завантаження звіту',
        desc: 'Натисніть кнопку генерації — файл <strong>.docx автоматично завантажиться</strong> на ваш пристрій.',
        position: 'center'
      },
      {
        target: null,
        icon: '✅',
        title: 'Готово!',
        desc: 'Тепер ви знаєте як формувати звіти. Сформований документ містить всі дані з журналу польотів.',
        position: 'center'
      }
    ],

    analytics: [
      {
        target: null,
        icon: '📈',
        title: 'Аналітика польотів',
        desc: 'Ця сторінка показує <strong>статистику та графіки</strong> по вильотах: кількість, тривалість, результативність.',
        position: 'center'
      },
      {
        target: null,
        icon: '🔍',
        title: 'Фільтри',
        desc: 'Використовуйте <strong>фільтри по даті та борту</strong> щоб переглядати статистику за потрібний період.',
        position: 'center'
      },
      {
        target: null,
        icon: '✅',
        title: 'Готово!',
        desc: 'Аналітика допомагає відстежувати ефективність роботи підрозділу в динаміці.',
        position: 'center'
      }
    ]
  };

  // ─── Engine ───────────────────────────────────────────────────────────────

  let steps = [];
  let current = 0;
  let running = false;
  let onFinishCb = null;

  function injectStyles() {
    if (document.getElementById('uav-tut-style')) return;
    const s = document.createElement('style');
    s.id = 'uav-tut-style';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function createDOM() {
    if (document.getElementById('uav-tutorial-overlay')) return;

    const backdrop = document.createElement('div');
    backdrop.id = 'uav-tutorial-backdrop';
    backdrop.style.display = 'none';
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) advance();
    });

    const spotlight = document.createElement('div');
    spotlight.id = 'uav-tutorial-spotlight';
    spotlight.style.display = 'none';

    const tooltip = document.createElement('div');
    tooltip.id = 'uav-tutorial-tooltip';
    tooltip.style.display = 'none';

    document.body.appendChild(backdrop);
    document.body.appendChild(spotlight);
    document.body.appendChild(tooltip);
  }

  function getEl(selector) {
    if (!selector) return null;
    try { return document.querySelector(selector); } catch (_) { return null; }
  }

  function positionTooltip(el, position) {
    const tooltip = document.getElementById('uav-tutorial-tooltip');
    tooltip.className = '';
    const MARGIN = 16;
    const tw = tooltip.offsetWidth || 320;
    const th = tooltip.offsetHeight || 200;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    if (!el || position === 'center') {
      tooltip.style.left = Math.max(MARGIN, (vw - tw) / 2) + 'px';
      tooltip.style.top  = Math.max(MARGIN, (vh - th) / 2) + 'px';
      tooltip.classList.add('arrow-none');
      return;
    }

    const r = el.getBoundingClientRect();
    let left, top;

    if (position === 'bottom') {
      left = r.left + r.width / 2 - tw / 2;
      top  = r.bottom + MARGIN;
      tooltip.classList.add('arrow-top');
    } else if (position === 'top') {
      left = r.left + r.width / 2 - tw / 2;
      top  = r.top - th - MARGIN;
      tooltip.classList.add('arrow-bottom');
    } else if (position === 'right') {
      left = r.right + MARGIN;
      top  = r.top + r.height / 2 - th / 2;
      tooltip.classList.add('arrow-left');
    } else if (position === 'left') {
      left = r.left - tw - MARGIN;
      top  = r.top + r.height / 2 - th / 2;
      tooltip.classList.add('arrow-right');
    } else {
      left = r.left + r.width / 2 - tw / 2;
      top  = r.bottom + MARGIN;
      tooltip.classList.add('arrow-top');
    }

    // Clamp to viewport
    left = Math.max(MARGIN, Math.min(left, vw - tw - MARGIN));
    top  = Math.max(MARGIN, Math.min(top,  vh - th - MARGIN));

    tooltip.style.left = left + 'px';
    tooltip.style.top  = top + 'px';
  }

  function positionSpotlight(el) {
    const spotlight = document.getElementById('uav-tutorial-spotlight');
    if (!el) {
      spotlight.style.display = 'none';
      return;
    }
    const PAD = 8;
    const r = el.getBoundingClientRect();
    spotlight.style.display = 'block';
    spotlight.style.left   = (r.left - PAD) + 'px';
    spotlight.style.top    = (r.top  - PAD) + 'px';
    spotlight.style.width  = (r.width  + PAD * 2) + 'px';
    spotlight.style.height = (r.height + PAD * 2) + 'px';
  }

  function buildDots() {
    return steps.map((_, i) => {
      let cls = 'tut-dot';
      if (i < current)  cls += ' done';
      if (i === current) cls += ' active';
      return `<span class="${cls}"></span>`;
    }).join('');
  }

  function renderStep() {
    const step = steps[current];
    const el   = getEl(step.target);
    const isLast = current === steps.length - 1;

    const backdrop  = document.getElementById('uav-tutorial-backdrop');
    const spotlight = document.getElementById('uav-tutorial-spotlight');
    const tooltip   = document.getElementById('uav-tutorial-tooltip');

    backdrop.style.display  = 'block';
    spotlight.style.display = el ? 'block' : 'none';
    tooltip.style.display   = 'block';

    // Scroll element into view
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      setTimeout(() => positionSpotlight(el), 200);
    } else {
      spotlight.style.display = 'none';
    }

    const hasPrev = current > 0;
    tooltip.innerHTML = `
      <div class="tut-step-badge">
        🎓 Крок ${current + 1} / ${steps.length}
      </div>
      <span class="tut-icon">${step.icon || '💡'}</span>
      <div class="tut-title">${step.title}</div>
      <div class="tut-desc">${step.desc}</div>
      <div class="tut-footer">
        <div class="tut-progress">${buildDots()}</div>
        <div class="tut-btns">
          <button class="tut-btn-skip" onclick="UAVTutorial.stop()">Пропустити</button>
          ${hasPrev ? '<button class="tut-btn-prev" onclick="UAVTutorial.prev()">← Назад</button>' : ''}
          <button class="tut-btn-next ${isLast ? 'finish' : ''}" onclick="UAVTutorial.advance()">
            ${isLast ? '<i class="fa-solid fa-check mr-1"></i>Завершити' : 'Далі →'}
          </button>
        </div>
      </div>
    `;

    setTimeout(() => {
      positionTooltip(el, step.position || 'bottom');
      if (el) positionSpotlight(el);
    }, 250);
  }

  function advance() {
    if (!running) return;
    if (current < steps.length - 1) {
      current++;
      renderStep();
    } else {
      stop();
    }
  }

  function prev() {
    if (!running || current === 0) return;
    current--;
    renderStep();
  }

  function stop() {
    running = false;
    const backdrop  = document.getElementById('uav-tutorial-backdrop');
    const spotlight = document.getElementById('uav-tutorial-spotlight');
    const tooltip   = document.getElementById('uav-tutorial-tooltip');
    if (backdrop)  backdrop.style.display  = 'none';
    if (spotlight) spotlight.style.display = 'none';
    if (tooltip)   tooltip.style.display   = 'none';
    localStorage.setItem('uav_tutorial_done', '1');
    if (typeof onFinishCb === 'function') onFinishCb();
  }

  function start(stepsArr, onFinish) {
    if (!stepsArr || stepsArr.length === 0) return;
    injectStyles();
    createDOM();
    steps = stepsArr;
    current = 0;
    running = true;
    onFinishCb = onFinish || null;
    renderStep();
  }

  function startPage(page, force) {
    if (!force && localStorage.getItem('uav_tutorial_done') === '1') return;
    const s = PAGE_STEPS[page];
    if (s) start(s);
  }

  function addHelpButton(page) {
    injectStyles();
    if (document.getElementById('uav-tutorial-help-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'uav-tutorial-help-btn';
    btn.title = 'Показати навчання';
    btn.textContent = '?';
    btn.addEventListener('click', () => startPage(page, true));
    document.body.appendChild(btn);
  }

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    if (!running) return;
    if (e.key === 'ArrowRight' || e.key === 'Enter') advance();
    if (e.key === 'ArrowLeft')  prev();
    if (e.key === 'Escape')     stop();
  });

  // Reposition on resize
  window.addEventListener('resize', () => {
    if (!running) return;
    const step = steps[current];
    const el   = getEl(step.target);
    positionTooltip(el, step.position || 'bottom');
    positionSpotlight(el);
  });

  // ─── Public API ───────────────────────────────────────────────────────────
  global.UAVTutorial = { start, startPage, addHelpButton, advance, prev, stop, PAGE_STEPS };

})(window);
