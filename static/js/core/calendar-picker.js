class CalendarPicker {
  constructor(inputSelector, options = {}) {
    this.input = typeof inputSelector === 'string'
      ? document.querySelector(inputSelector)
      : inputSelector;

    if (!this.input) return;

    this.format   = options.format   || 'dd/mm/yyyy';
    this.minYear  = options.minYear  || 1950;
    this.maxYear  = options.maxYear  || 2100;
    this.selectedDate = null;

    // Si ya tiene un picker adjunto, no crear otro
    if (this.input._calendarPicker) return;
    this.input._calendarPicker = this;

    this._onDocClick = (e) => {
      if (!this.container.contains(e.target) && e.target !== this.input) {
        this.hidePicker();
      }
    };

    this.createPicker();
    this.attachEvents();
  }

  createPicker() {
    this.container = document.createElement('div');
    this.container.className = 'calendar-picker hidden';
    this.container.innerHTML = `
      <div class="calendar-header">
        <button type="button" class="calendar-nav" data-dir="prev">&#8249;</button>
        <div class="calendar-month-year">
          <select class="calendar-month"></select>
          <select class="calendar-year"></select>
        </div>
        <button type="button" class="calendar-nav" data-dir="next">&#8250;</button>
      </div>
      <div class="calendar-weekdays">
        <div>Lu</div><div>Ma</div><div>Mi</div><div>Ju</div>
        <div>Vi</div><div>Sa</div><div>Do</div>
      </div>
      <div class="calendar-days"></div>
    `;

    // Adjuntar al body para evitar problemas con overflow:hidden/auto en modales
    document.body.appendChild(this.container);

    this.fillMonths();
    this.fillYears();
    this.renderDays();
  }

  fillMonths() {
    const months = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                    'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
    const select = this.container.querySelector('.calendar-month');
    months.forEach((m, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = m;
      select.appendChild(opt);
    });
  }

  fillYears() {
    const select = this.container.querySelector('.calendar-year');
    for (let y = this.maxYear; y >= this.minYear; y--) {
      const opt = document.createElement('option');
      opt.value = y;
      opt.textContent = y;
      select.appendChild(opt);
    }
  }

  renderDays() {
    const month = parseInt(this.container.querySelector('.calendar-month').value);
    const year  = parseInt(this.container.querySelector('.calendar-year').value);

    const firstDay    = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today       = new Date();

    const daysContainer = this.container.querySelector('.calendar-days');
    daysContainer.innerHTML = '';

    for (let i = 0; i < (firstDay === 0 ? 6 : firstDay - 1); i++) {
      const day = document.createElement('div');
      day.className = 'calendar-day disabled';
      daysContainer.appendChild(day);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const day = document.createElement('button');
      day.type = 'button';
      day.textContent = d;
      day.dataset.date = `${d}/${month + 1}/${year}`;

      const isToday =
        d === today.getDate() &&
        month === today.getMonth() &&
        year === today.getFullYear();

      const isSelected =
        this.selectedDate &&
        d === this.selectedDate.d &&
        month === this.selectedDate.m &&
        year === this.selectedDate.y;

      let cls = 'calendar-day';
      if (isToday && !isSelected) cls += ' today';
      if (isSelected) cls += ' selected';

      day.className = cls;
      day.addEventListener('click', (e) => this.selectDate(e));
      daysContainer.appendChild(day);
    }
  }

  selectDate(e) {
    e.preventDefault();
    const [d, m, y] = e.target.dataset.date.split('/');
    this.selectedDate = { d: parseInt(d), m: parseInt(m) - 1, y: parseInt(y) };
    this.input.value = `${d.padStart(2,'0')}/${m.padStart(2,'0')}/${y}`;
    this.hidePicker();
    this.renderDays();
    this.input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  adjustPosition() {
    const rect    = this.input.getBoundingClientRect();
    const pickerH = this.container.offsetHeight || 320;
    const pickerW = this.container.offsetWidth  || 300;

    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;

    // Vertical
    let top;
    if (spaceBelow >= pickerH + 8 || spaceBelow >= spaceAbove) {
      top = rect.bottom + window.scrollY + 6;
    } else {
      top = rect.top + window.scrollY - pickerH - 6;
    }

    // Horizontal
    let left = rect.left + window.scrollX;
    if (left + pickerW > window.innerWidth - 8) {
      left = window.innerWidth - pickerW - 8 + window.scrollX;
    }
    if (left < 8) left = 8;

    this.container.style.position = 'absolute';
    this.container.style.top      = top  + 'px';
    this.container.style.left     = left + 'px';
    this.container.style.right    = 'auto';
    this.container.style.bottom   = 'auto';
    this.container.style.zIndex   = '99999';
  }

  showPicker() {
    // Inicializar al valor actual del input si existe
    if (this.input.value) {
      const parts = this.input.value.split('/');
      if (parts.length === 3) {
        const m = parseInt(parts[1]) - 1;
        const y = parseInt(parts[2]);
        if (!isNaN(m) && !isNaN(y)) {
          this.container.querySelector('.calendar-month').value = m;
          this.container.querySelector('.calendar-year').value  = y;
          this.selectedDate = { d: parseInt(parts[0]), m, y };
          this.renderDays();
        }
      }
    }
    this.container.classList.remove('hidden');
    requestAnimationFrame(() => this.adjustPosition());
  }

  hidePicker() {
    this.container.classList.add('hidden');
  }

  togglePicker() {
    if (this.container.classList.contains('hidden')) {
      this.showPicker();
    } else {
      this.hidePicker();
    }
  }

  attachEvents() {
    this.input.addEventListener('click', (e) => {
      e.stopPropagation();
      this.togglePicker();
    });

    this.container.querySelectorAll('.calendar-nav').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const dir = e.currentTarget.dataset.dir;
        let month = parseInt(this.container.querySelector('.calendar-month').value);
        let year  = parseInt(this.container.querySelector('.calendar-year').value);

        if (dir === 'prev') {
          month--;
          if (month < 0) { month = 11; year--; }
        } else {
          month++;
          if (month > 11) { month = 0; year++; }
        }

        this.container.querySelector('.calendar-month').value = month;
        this.container.querySelector('.calendar-year').value  = year;
        this.renderDays();
      });
    });

    this.container.querySelector('.calendar-month').addEventListener('change', () => this.renderDays());
    this.container.querySelector('.calendar-year').addEventListener('change',  () => this.renderDays());

    // Cerrar al hacer click fuera
    document.addEventListener('click', this._onDocClick);

    // Reposicionar al hacer scroll o resize
    window.addEventListener('scroll', () => {
      if (!this.container.classList.contains('hidden')) this.adjustPosition();
    }, true);
    window.addEventListener('resize', () => {
      if (!this.container.classList.contains('hidden')) this.adjustPosition();
    });
  }

  destroy() {
    document.removeEventListener('click', this._onDocClick);
    if (this.container && this.container.parentNode) {
      this.container.parentNode.removeChild(this.container);
    }
    if (this.input) delete this.input._calendarPicker;
  }
}