// Standalone prototype refinements only. No API, persistence or application imports.
modal.setAttribute('aria-labelledby', 'modalTitle');
const style = document.createElement('style');
style.textContent = '.desktop details.active>summary,.navlinks details.active>summary{background:#e8f5e8;color:#096e8d}.scenario{margin:12px 0}.scenario select{max-width:300px}';
document.head.append(style);

// A destination change must retain focus on its heading, not restore an old trigger.
const originalNavigate = navigate;
navigate = function(id) { trigger = null; originalNavigate(id); };
const originalNavigation = navigation;
navigation = function() {
  originalNavigation();
  const restricted = ['none', 'platform'].includes(settings.role);
  document.querySelector('#orgBtn').hidden = restricted;
  document.querySelector('.skip').textContent = t('Aller au contenu', 'Skip to content');
  document.querySelector('#closeBtn').setAttribute('aria-label', t('Fermer', 'Close'));
  document.querySelector('#desktop').setAttribute('aria-label', t('Navigation principale', 'Main navigation'));
  document.querySelector('#bottom').setAttribute('aria-label', t('Navigation mobile', 'Mobile navigation'));
};
const originalLinks = links;
links = function() {
  const container = document.createElement('div');
  container.innerHTML = originalLinks();
  container.querySelectorAll('details').forEach(group => {
    if(group.querySelector('[aria-current]')) group.classList.add('active');
  });
  return container.innerHTML;
};
const originalMenu = menu;
menu = function() {
  originalMenu();
  if(['none','platform'].includes(settings.role)) body.querySelector('[data-action="org"]')?.remove();
};
const originalOrg = org;
org = function() { if(!['none','platform'].includes(settings.role)) originalOrg(); };
document.querySelector('#menuBtn').onclick = () => menu();
document.querySelector('#orgBtn').onclick = () => org();
const originalRender = render;
render = function() {
  originalRender();
  if(settings.role === 'none') {
    content.innerHTML = `<section class="panel"><h1 tabindex="-1">${name('account')}</h1><p>Camille</p><h2>${t('Aucune organisation accessible','No accessible organization')}</h2><p>${t('Votre compte reste accessible. Demandez une invitation pour rejoindre un espace.','Your account remains accessible. Request an invitation to join a workspace.')}</p></section>`;
  }
};

function syncSelection() {
  const all = document.querySelector('#all');
  if(!all) return;
  const available = companies.length - added.size;
  all.checked = available > 0 && selected.size === available;
  all.indeterminate = selected.size > 0 && selected.size < available;
  all.disabled = available === 0;
  all.parentElement.lastChild.textContent = t('Sélectionner les résultats disponibles','Select available results');
}
document.addEventListener('change', syncSelection);

let scenario = 'success';
const originalSearch = renderSearch;
renderSearch = function() {
  originalSearch();
  syncSelection();
  if(!applied) { scenario = 'success'; return; }
  const options = [['success','Résultats','Results'],['loading','Chargement','Loading'],['empty','Aucun résultat','No results'],['error','Erreur réseau','Network error'],['quota','Quota atteint','Quota reached'],['cancelled','Recherche interrompue','Search interrupted']];
  const box = document.createElement('section');
  box.className = 'notice scenario';
  box.innerHTML = `<label>${t('Atelier V2 — état simulé','V2 workshop — simulated state')} <select id="scenario">${options.map(([v,fr,en])=>`<option value="${v}" ${scenario===v?'selected':''}>${t(fr,en)}</option>`).join('')}</select></label>`;
  content.children[2]?.before(box);
  box.querySelector('select').onchange = e => { scenario=e.target.value; selected.clear(); renderSearch(); document.querySelector('#scenario').focus(); };
  if(scenario==='success') return;
  const result = content.querySelector('.list');
  const messages = {
    loading: t('Recherche en cours…','Searching…'),
    empty: t('Aucun établissement trouvé. Essayez une autre zone ou un autre terme.','No businesses found. Try another area or term.'),
    error: t('La recherche a échoué. Vos paramètres sont conservés.','Search failed. Your parameters have been kept.'),
    quota: t('Quota de recherche atteint. Consultez Quotas et usage.','Search quota reached. See Quotas and usage.'),
    cancelled: t('Recherche interrompue. Aucun résultat ajouté.','Search interrupted. No results added.')
  };
  result.innerHTML = `<div role="status"><h2>${messages[scenario]}</h2></div>`;
  const action = document.createElement('button');
  action.textContent = scenario==='loading'?t('Interrompre','Cancel search'):scenario==='quota'?name('usage'):scenario==='empty'?t('Modifier les paramètres','Edit parameters'):t('Réessayer (simulation)','Retry (simulation)');
  result.append(action);
  action.onclick = () => {
    if(scenario==='quota') { navigate('usage'); return; }
    if(scenario==='empty') { params(); return; }
    scenario=scenario==='loading'?'cancelled':'success'; renderSearch(); content.querySelector('h1').focus();
  };
};
// A submitted search always starts a fresh successful demonstration.
document.addEventListener('submit', e => { if(e.target.id==='params') scenario='success'; }, true);
render();
