const I18n = {
  lang: 'ja',
  data: {},
  async load(lang) {
    this.lang = lang;
    const resp = await fetch(`/api/i18n/${lang}`);
    this.data = await resp.json();
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      if (this.data[key]) el.textContent = this.data[key];
    });
  },
  t(key) { return this.data[key] || key; }
};
