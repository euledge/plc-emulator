document.addEventListener('DOMContentLoaded', async () => {
  await I18n.load('ja');

  document.querySelectorAll('#lang-switcher button').forEach(btn => {
    btn.addEventListener('click', async () => {
      document.querySelectorAll('#lang-switcher button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await I18n.load(btn.dataset.lang);
    });
  });

  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.getElementById('page-' + link.dataset.page).classList.add('active');
    });
  });

  SettingsPage.init();
  DeviceMonitor.init();
  CommLog.init();
  ScriptEditor.init();
});
