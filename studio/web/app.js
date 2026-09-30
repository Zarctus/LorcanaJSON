const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const icons = {
 dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 cards: '<rect x="7" y="3" width="13" height="17" rx="2"/><path d="M4 6 2 19a2 2 0 0 0 2 2l9 1M11 8h5m-5 4h5"/>',
 edit: '<path d="m15 4 5 5M4 16 16 4a2 2 0 0 1 4 4L8 20l-5 1Z"/>',
 activity: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
 box: '<path d="m3 7 9-4 9 4v11l-9 4-9-4Zm0 0 9 4 9-4m-9 4v11M7 5l10 4"/>',
 settings: '<path d="m10 3-1 3-3 1-3-1-1 4 2 2-1 3 2 3 3-1 3 2 1 3 4-1 1-3 3-1 2-3-2-2V9l1-3-3-2-3 1-2-2Z"/><circle cx="12" cy="12" r="3"/>',
 globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
 refresh: '<path d="M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3"/>',
 arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
 download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
 search: '<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/>',
 check: '<path d="m5 12 4 4L19 6"/>',
 play: '<path d="m8 4 13 8-13 8Z"/>',
 close: '<path d="m6 6 12 12M6 18 18 6"/>',
 clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
 folder: '<path d="M3 7V4h6l3 3h9v14H3Z"/>',
 spark: '<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3ZM20 2v4m-2-2h4"/>',
 code: '<path d="m7 7-5 5 5 5m10-10 5 5-5 5M14 3l-4 18"/>',
 grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 list: '<path d="M8 5h13M8 12h13M8 19h13M3 5h1M3 12h1M3 19h1"/>',
 shield: '<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Z"/><path d="m8 12 3 3 5-6"/>',
 chevron: '<path d="m9 5 7 7-7 7"/>',
 ink: '<path d="M12 2C10 6 4 11 4 15a8 8 0 0 0 16 0c0-4-6-9-8-13Z"/>',
 info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-11v1"/>',
 heart: '<path d="M12 21 3 12C-2 5 7-1 12 6c5-7 14-1 9 6Z"/>',
 star: '<path d="m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z"/>'
};
const icon = name => `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.cards}</svg>`;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = n => new Intl.NumberFormat('fr-FR').format(n);
const date = s => s ? new Date(s).toLocaleDateString('fr-FR', {day:'numeric',month:'long',year:'numeric'}) : 'Aucune génération';
const size = n => n > 1e6 ? `${(n / 1e6).toFixed(1)} Mo` : `${Math.round(n / 1e3)} Ko`;
const labels = {home:'Vue d’ensemble',catalog:'Catalogue',corrections:'Corrections',jobs:'Traitements',exports:'Exports',settings:'Paramètres'};
const actionLabels = {check:'Rechercher les mises à jour',download:'Télécharger les données',update:'Mettre à jour la base',parse:'Analyser les cartes',verify:'Vérifier les données',updateExternalLinks:'Actualiser les liens externes'};
const state = {page:'home', language:localStorage.getItem('fred-language') || 'fr', catalog:null, search:'', set:'', color:'', rarity:'', sort:'new', view:'grid', limit:48, job:null, selected:null};
const token = location.hash.slice(1) || sessionStorage.getItem('fred-token') || '';
if (token) sessionStorage.setItem('fred-token', token);
history.replaceState(null, '', location.pathname);
let loadSequence = 0;
let detailSequence = 0;
let toastTimer;

async function api(path, body) {
 const response = await fetch(path, {method:body === undefined ? 'GET':'POST', headers:{'X-Studio-Token':token, ...(body === undefined ? {} : {'Content-Type':'application/json'})}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
 const data = await response.json();
 if (!response.ok) throw new Error(data.error || 'Le moteur local ne répond pas.');
 return data;
}
function toast(message, error=false) { const el=$('#toast'); el.textContent=message; el.className=`visible ${error?'error':''}`; if(!el.matches(':popover-open'))el.showPopover(); clearTimeout(toastTimer); toastTimer=setTimeout(()=>{el.className='';el.hidePopover();},6500); }
function image(card) { return `/images/${state.language}/${card.id}.jpg`; }
function badge(card) { return /enchant|enchanted|iconi|epic|épique/i.test(card.rarity || '') ? 'special' : ''; }
function cardTile(c) { return `<button class="card-tile ${badge(c)}" data-card="${c.id}" aria-label="Ouvrir ${escapeHtml(c.fullName)}"><div class="card-art"><img src="${image(c)}" alt="${escapeHtml(c.fullName)}" loading="lazy"><span class="card-open">${icon('arrow')}</span>${c.corrected?'<span class="correction-mark" title="Règles de correction présentes">✦</span>':''}</div><div class="card-caption"><strong>${escapeHtml(c.name)}</strong><span>${escapeHtml(c.version || c.type)}</span><div><span class="rarity-dot ${badge(c)}"></span>${escapeHtml(c.rarity)}<span class="card-number">#${c.id}</span></div></div></button>`; }
function header(eyebrow,title,description,actions='') { return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><div class="heading-actions">${actions}</div></div>`; }
function empty(title, description, action='') { return `<div class="empty">${icon('cards')}<h3>${title}</h3><p>${description}</p>${action}</div>`; }
function cardsSorted(cards=state.catalog.cards) { return [...cards].sort((a,b)=>state.sort==='name' ? a.fullName.localeCompare(b.fullName,'fr') : state.sort==='id' ? a.id-b.id : b.id-a.id); }

async function load() {
 const sequence = ++loadSequence;
 const lang = state.language;
 try {
  const catalog = await api(`/api/catalog?language=${lang}`);
  if (sequence !== loadSequence) return;
  state.catalog = catalog;
  $('#language').value=lang;
  $('#nav-count').textContent=number(catalog.cards.length);
  $('#connection').textContent=`Base locale · ${number(catalog.cards.length)} cartes`;
  $('#footer-date').textContent=`Générée le ${date(catalog.metadata.generatedOn)}`;
  render();
 } catch(e) { if(sequence!==loadSequence)return; $('#content').innerHTML=empty('Le studio n’est pas connecté',escapeHtml(e.message),'<button class="button primary" data-reload>Réessayer</button>'); $('#connection').textContent='Connexion interrompue'; }
}
function navigate(page) {
 state.page=page; state.limit=48;
 $$('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
 $('#breadcrumb').textContent=labels[page];
 render(); window.scrollTo({top:0});
}
function render() {
 if(!state.catalog) return;
 const renderers={home:renderHome,catalog:renderCatalog,corrections:renderCatalog,jobs:renderJobs,exports:renderExports,settings:renderSettings};
 renderers[state.page]();
}
function renderHome() {
 const d=state.catalog; const corrected=d.cards.filter(c=>c.corrected).length;
 const editions=Object.keys(d.sets).length;
 // Identifiants communs aux langues : une princesse par emplacement,
 // avec d’autres éditions en repli si la carte préférée n’est pas disponible.
 const byId = new Map(d.cards.map(card => [card.id, card]));
 const princessEditions = groups => groups.map(ids => ids.map(id => byId.get(id)).find(Boolean)).filter(Boolean);
 const picks = princessEditions([[1878,2685],[2430,2150,911],[2699,2144,1650]]);
 const princesses = princessEditions([[3507,2425,896,421],[1638,213],[2158,1885,903],[1176,422],[1405,2668]]);
 $('#content').innerHTML=header('VOTRE ATELIER LORCANA','Chaque carte compte.','Tout votre univers de cartes, dans un seul espace.',`<button class="button" data-page="exports">${icon('box')}Mes exports</button>`)+`
  <section class="hero"><div class="hero-grain"></div><div class="hero-content"><span class="pill">${icon('spark')} LE STUDIO EST À VOUS</span><h2>De l’encre.<br>Des cartes.<br><em>Des possibilités.</em></h2><p>Explorez votre catalogue, affinez chaque détail<br>et donnez vie à vos données Lorcana.</p><div class="hero-actions"><button class="button primary" data-page="catalog">Explorer le catalogue ${icon('arrow')}</button><button class="button ghost" data-action="check">${icon('refresh')}Rechercher les nouveautés</button></div></div><div class="hero-art" aria-label="Raiponce, Ariel et Belle : les princesses du studio">${picks.map((c,i)=>`<img class="hero-card hero-card-${i}" src="${image(c)}" alt="${escapeHtml(c.fullName)}">`).join('')}<span class="orbit orbit-one"></span><span class="orbit orbit-two"></span><span class="art-caption">DISNEY LORCANA <span>✦</span> COLLECTION LOCALE</span></div></section>
  <section class="stats" aria-label="Statistiques de la base"><div class="stat"><span class="stat-icon violet">${icon('cards')}</span><div><span>Cartes dans la base</span><strong>${number(d.cards.length)}<small>${state.language.toUpperCase()}</small></strong></div></div><div class="stat"><span class="stat-icon blue">${icon('box')}</span><div><span>Extensions & séries</span><strong>${editions}<small>cataloguées</small></strong></div></div><div class="stat"><span class="stat-icon peach">${icon('edit')}</span><div><span>Cartes avec corrections</span><strong>${number(corrected)}<small>règles présentes</small></strong></div></div><div class="stat"><span class="stat-icon mint">${icon('globe')}</span><div><span>Langues disponibles</span><strong>${d.languages.filter(l=>l.available).length}<small>${d.languages.filter(l=>l.available).map(l=>l.code.toUpperCase()).join(' · ')}</small></strong></div></div></section>
  <div class="home-bottom"><section class="recent-section"><div class="section-heading"><h2>Les princesses à l’honneur <span class="subtle-tag">SÉLECTION DU STUDIO</span></h2><button class="text-button" data-page="catalog">Tout explorer ${icon('arrow')}</button></div><div class="recent-grid">${princesses.map(cardTile).join('') || empty('Votre catalogue attend ses cartes','Téléchargez puis analysez les données depuis Traitements.')}</div></section><aside class="quick-panel"><div class="section-heading"><h2>Au fil de l’encre</h2>${icon('spark')}</div><p>Un catalogue à jour.<br>Des données qui font la différence.</p><button class="quick-action" data-page="jobs"><span class="quick-icon">${icon('refresh')}</span><span>Actualiser la base<small>Téléchargement & analyse</small></span>${icon('chevron')}</button><button class="quick-action" data-page="corrections"><span class="quick-icon">${icon('edit')}</span><span>Ouvrir l’atelier<small>Relire, comparer, corriger</small></span>${icon('chevron')}</button><div class="generation-note">${icon('clock')}<span>Dernière génération<strong>${date(d.metadata.generatedOn)}</strong></span></div></aside></div>`;
}
function renderCatalog() {
 const correction=state.page==='corrections';
 const unique=key=>[...new Set(state.catalog.cards.map(c=>c[key]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr'));
 const options=(values,selected)=>values.map(v=>`<option ${selected===v?'selected':''} value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
 $('#content').innerHTML=header(correction?'L’ATELIER DES DÉTAILS':'VOTRE COLLECTION DE DONNÉES',correction?'La précision, carte par carte.':'Le catalogue.',correction?'Comparez les écarts avec la référence, puis appliquez et vérifiez les corrections d’un clic.':'Parcourez les cartes et ouvrez leurs données dans l’atelier.',`<span class="heading-count">${number(state.catalog.cards.length)} <small>cartes locales</small></span>`)+`
 ${correction?`<div class="review-scope"><button data-review-scope="review" class="${state.reviewScope==='review'?'active':''}">${icon('spark')}À relire · propositions</button><button data-review-scope="rules" class="${state.reviewScope==='rules'?'active':''}">${icon('edit')}Règles existantes</button><span>Les écarts sont des pistes à contrôler, pas des erreurs confirmées.</span></div>`:''}<section class="catalog-toolbar"><label class="search-field">${icon('search')}<input id="search" type="search" placeholder="Un nom, un univers, un identifiant…" value="${escapeHtml(state.search)}" aria-label="Rechercher une carte"><kbd>Ctrl K</kbd></label><select id="set-filter" aria-label="Extension"><option value="">Toutes les extensions</option>${Object.entries(state.catalog.sets).map(([k,v])=>`<option value="${escapeHtml(k)}" ${state.set===k?'selected':''}>${escapeHtml(v.name || k)}</option>`).join('')}</select><select id="color-filter" aria-label="Couleur d’encre"><option value="">Toutes les encres</option>${options(unique('color'),state.color)}</select><select id="rarity-filter" aria-label="Rareté"><option value="">Toutes les raretés</option>${options(unique('rarity'),state.rarity)}</select></section>
 <div class="catalog-subbar"><span id="result-count"></span><div><button class="text-button" id="reset-filters">Réinitialiser</button><select id="sort" aria-label="Trier les cartes"><option value="new" ${state.sort==='new'?'selected':''}>Identifiants décroissants</option><option value="id" ${state.sort==='id'?'selected':''}>Identifiants croissants</option><option value="name" ${state.sort==='name'?'selected':''}>Nom de la carte</option></select><div class="view-toggle"><button data-view="grid" class="icon-button ${state.view==='grid'?'selected':''}" aria-label="Vue en grille" aria-pressed="${state.view==='grid'}">${icon('grid')}</button><button data-view="list" class="icon-button ${state.view==='list'?'selected':''}" aria-label="Vue en liste" aria-pressed="${state.view==='list'}">${icon('list')}</button></div></div></div><div id="catalog-results"></div>`;
 updateResults();
 if(correction)loadReview();
 $('#search').addEventListener('input',e=>{state.search=e.target.value;state.limit=48;updateResults();});
 [['set-filter','set'],['color-filter','color'],['rarity-filter','rarity'],['sort','sort']].forEach(([id,key])=>$('#'+id).addEventListener('change',e=>{state[key]=e.target.value;state.limit=48;updateResults();}));
}
function updateResults() {
 if(state.page==='corrections' && state.reviewScope==='review' && state.reviewLanguage!==state.language){$('#catalog-results').innerHTML='<div class="loading"><span class="spinner"></span>Comparaison des cartes avec leurs références…</div>';return;}
 const normalize=s=>String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 const q=normalize(state.search);
 const cards=cardsSorted().filter(c=>(state.page!=='corrections'||(state.reviewScope==='rules'?c.corrected:state.review?.has(c.id)))&&(!state.set||c.setCode===state.set)&&(!state.color||c.color===state.color)&&(!state.rarity||c.rarity===state.rarity)&&(!q||normalize(`${c.fullName} ${c.story} ${c.id}`).includes(q)));
 $('#result-count').innerHTML=`<strong>${number(cards.length)}</strong> carte${cards.length===1?'':'s'} ${state.page==='corrections'?(state.reviewScope==='rules'?'avec règles de correction':'à relire'):'dans cette sélection'}`;
 state.visibleIds=cards.map(c=>c.id);
 const visible=cards.slice(0,state.limit);
 $('#catalog-results').innerHTML=!cards.length?empty('Aucune carte dans cette sélection','Essayez un autre nom ou réinitialisez les filtres.'):state.view==='grid'?`<div class="catalog-grid">${visible.map(cardTile).join('')}</div>`:`<div class="card-list">${visible.map(c=>`<button class="card-row" data-card="${c.id}"><img src="${image(c)}" alt="" loading="lazy"><span><strong>${escapeHtml(c.name)}</strong><small>${escapeHtml(c.version || c.type)}</small></span><span>${escapeHtml(c.color)}</span><span>${escapeHtml(c.rarity)}</span><span>#${c.id}</span>${icon('chevron')}</button>`).join('')}</div>`;
 if(cards.length>state.limit) $('#catalog-results').insertAdjacentHTML('beforeend',`<div class="load-more"><button class="button" id="load-more">Afficher 48 cartes supplémentaires ${icon('arrow')}</button><small>${visible.length} sur ${number(cards.length)}</small></div>`);
}

async function openCard(id, tab='data') {
 const seq=++detailSequence;
 const dialog=$('#card-dialog');
 if(!dialog.open)dialog.showModal();
 $('#detail-content').innerHTML='<button class="icon-button modal-close" data-close aria-label="Fermer">'+icon('close')+'</button><div class="loading"><span class="spinner"></span>Ouverture de la carte…</div>';
 try {
  const detail=await api(`/api/card?language=${state.language}&id=${id}`);
  if(seq!==detailSequence||!dialog.open)return;
  state.selected=detail;
  renderDetail(tab);
 } catch(e){ $('#detail-content').innerHTML=`<button class="icon-button modal-close" data-close aria-label="Fermer">${icon('close')}</button>${empty('Carte indisponible',escapeHtml(e.message))}`; }
}
function renderDetail(tab='data') {
 state.detailTab=tab;
 const d=state.selected,c=d.card;
 $('#detail-content').innerHTML=`<div class="detail-visual"><div class="detail-kicker">${icon('cards')} ${state.language.toUpperCase()} · #${c.id}</div><img class="detail-card-image" src="${image(c)}" alt="${escapeHtml(c.fullName)}"><span class="detail-image-caption">${escapeHtml(c.fullIdentifier)} · Image locale</span><div class="detail-tools"><button class="button" data-card-direction="-1" aria-label="Carte précédente">←</button><button class="button" data-zoom aria-pressed="false" title="Agrandir l’image">${icon('search')}Zoom</button><button class="button" data-card-direction="1" aria-label="Carte suivante">→</button></div></div><div class="detail-panel"><button class="icon-button modal-close" data-close aria-label="Fermer la fiche">${icon('close')}</button><div class="eyebrow">${escapeHtml(state.catalog.sets[c.setCode]?.name || `Série ${c.setCode}`)}</div><h2 id="detail-title">${escapeHtml(c.name)}</h2><p class="detail-version">${escapeHtml(c.version || c.type)}</p><div class="detail-badges"><span>${escapeHtml(c.rarity)}</span><span>${escapeHtml(c.color)}</span><span>${escapeHtml(c.type)}</span></div><div class="detail-stats">${[['ink','Coût',c.cost],['activity','Force',c.strength],['shield','Volonté',c.willpower],['star','Lore',c.lore]].filter(x=>x[2]!==undefined).map(([i,t,v])=>`<div>${icon(i)}<strong>${v}</strong><span>${t}</span></div>`).join('')}</div><div class="tabs" role="tablist"><button role="tab" aria-selected="${tab==='data'}" data-tab="data">La carte</button><button role="tab" aria-selected="${tab==='edit'}" data-tab="edit">Atelier de correction</button><button role="tab" aria-selected="${tab==='json'}" data-tab="json">JSON</button></div><div id="detail-tab" class="detail-tab" role="tabpanel"></div></div>`;
 const panel=$('#detail-tab');
 if(tab==='data')panel.innerHTML=`<div class="card-text">${c.abilities?.map(a=>`<div class="ability"><h3>${escapeHtml(a.name || a.keyword || 'Capacité')}</h3><p>${escapeHtml(a.effect || a.fullText)}</p></div>`).join('')||''}${c.effects?.map(e=>`<p>${escapeHtml(e)}</p>`).join('')||''}${!c.abilities?.length&&!c.effects?.length?`<p>${escapeHtml(c.fullText || 'Cette carte ne possède pas de texte de capacité.')}</p>`:''}</div>${c.flavorText?`<blockquote>${escapeHtml(c.flavorText)}</blockquote>`:''}<dl class="detail-meta"><div><dt>Univers</dt><dd>${escapeHtml(c.story || '—')}</dd></div><div><dt>Illustration</dt><dd>${escapeHtml(c.artistsText || '—')}</dd></div><div><dt>Sous-types</dt><dd>${escapeHtml(c.subtypesText || '—')}</dd></div></dl><button class="button primary full-width" data-tab="edit">${icon('edit')}Ouvrir dans l’atelier</button>`;
 if(tab==='json')panel.innerHTML=`<div class="section-heading"><span class="muted">Données générées · lecture seule</span><button class="text-button" id="copy-json">${icon('code')}Copier</button></div><pre class="json-view">${escapeHtml(JSON.stringify(c,null,2))}</pre>`;
 if(tab==='edit') renderWorkshop(panel);
}
function renderAdvancedEditor(panel) {
 const d=state.selected,c=d.card;
 panel.innerHTML=`<div class="notice">${icon('info')}<span>Enregistrez une règle persistante, puis relancez l’analyse de la carte pour l’appliquer. Les règles existantes sont conservées.</span></div><form id="correction-form"><label>Champ à corriger<select id="correction-field"><option value="abilities">Capacités</option><option value="effects">Effets</option><option value="flavorText">Texte d’ambiance</option><option value="name">Nom</option><option value="version">Sous-titre</option><option value="artistsText">Illustrateur</option></select></label><details class="field-source"><summary>Afficher le contenu actuel du champ</summary><pre id="field-source"></pre></details><label>Texte à remplacer<textarea id="before" rows="2" placeholder="Copiez le passage exact à corriger…" required></textarea></label><label>Remplacer par<textarea id="after" rows="2" placeholder="Votre correction…" required></textarea></label><div class="form-actions"><button class="button" type="submit">Prévisualiser</button><button class="button primary" type="button" id="save-correction" disabled>${icon('check')}Enregistrer la règle</button></div><div id="correction-preview" aria-live="polite"></div></form><details class="existing-rules"><summary>Règles existantes pour cette carte (${Object.keys(d.corrections).length} champs)</summary><pre>${escapeHtml(JSON.stringify(d.corrections,null,2))}</pre></details><button class="text-button" data-action="parse" data-ids="${c.id}">${icon('play')}Relancer l’analyse de cette carte</button>`;
 {
  const source=()=>{$('#field-source').textContent=JSON.stringify(c[$('#correction-field').value] ?? 'Champ absent',null,2);$('#save-correction').disabled=true;$('#correction-preview').innerHTML='';};
  source(); $('#correction-field').addEventListener('change',source);
  $('#correction-form').addEventListener('input',()=>{$('#save-correction').disabled=true;$('#correction-preview').innerHTML='';});
  $('#correction-form').addEventListener('submit',previewCorrection);
 }
}
function correctionPayload() { return {language:state.language,id:state.selected.card.id,revision:state.selected.revision,field:$('#correction-field').value,before:$('#before').value,after:$('#after').value}; }
async function previewCorrection(event) {
 event.preventDefault();
 try { const preview=await api('/api/corrections/preview',correctionPayload()); $('#correction-preview').innerHTML=`<div class="preview-label">${icon('check')}${preview.matches} remplacement(s) dans les données actuelles</div><pre>${escapeHtml(typeof preview.after==='string'?preview.after:JSON.stringify(preview.after,null,2))}</pre><small>Le texte OCR de la prochaine analyse peut différer : vérifiez ensuite le résultat.</small>`; $('#save-correction').disabled=false; } catch(e){toast(e.message,true);}
}
async function saveCorrection(button) {
 button.disabled=true;
 try { const result=await api('/api/corrections',correctionPayload()); Object.assign(state.selected,{revision:result.revision,corrections:result.corrections});toast('Règle enregistrée. Une sauvegarde du fichier précédent a été créée.');renderDetail('edit');await load(); } catch(e){toast(e.message,true);button.disabled=false;}
}

function renderJobs() {
 $('#content').innerHTML=header('LE MOTEUR DE VOTRE BASE','Place à l’action.','Téléchargez, analysez et vérifiez vos cartes. Un traitement à la fois.')+`
 <div class="jobs-layout"><section class="panel job-config"><div class="section-heading"><h2>Nouveau traitement</h2>${icon('activity')}</div><form id="job-form"><label>Opération<select id="job-action">${Object.entries(actionLabels).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><p id="action-description" class="field-help"></p><label id="ids-label" hidden>Identifiants des cartes <span class="optional">facultatif</span><input id="job-ids" placeholder="Ex. 1 12 20-30"><small>Vide : toutes les cartes de la langue sélectionnée.</small></label><label class="checkbox-label" id="cache-label" hidden><input id="job-cache" type="checkbox" checked>Utiliser le cache OCR disponible</label><div class="job-language">${icon('globe')}Langue du traitement <strong>${escapeHtml(state.catalog.languages.find(l=>l.code===state.language)?.label)}</strong></div><button type="submit" class="button primary full-width" id="run-job">${icon('play')}Lancer le traitement</button></form><div class="notice">${icon('info')}<span>La mise à jour et l’analyse régénèrent les fichiers de sortie. Les corrections sont appliquées par le moteur existant.</span></div></section><section class="panel job-console"><div class="section-heading"><h2>Journal d’exécution</h2><span class="live-tag" id="job-state">EN ATTENTE</span></div><div id="job-summary"></div><pre id="job-log" role="log" aria-label="Journal du traitement">Aucun traitement lancé. Votre prochain travail commence ici.</pre></section></div>`;
 const describe=()=>{const a=$('#job-action').value; const texts={check:'Compare les données officielles avec votre copie locale et signale les nouveautés.',download:'Télécharge les données officielles et les images manquantes.',update:'Recherche les changements et régénère les cartes ajoutées ou modifiées.',parse:'Relance la reconnaissance et la génération des données des cartes sélectionnées.',verify:'Compare les données générées avec les données de référence et signale les différences.',updateExternalLinks:'Actualise les correspondances avec les sites externes. Le jeton CardTrader doit être configuré dans le projet.'};$('#action-description').textContent=texts[a];$('#ids-label').hidden=!['parse','verify'].includes(a);$('#cache-label').hidden=!['parse','update'].includes(a);};
 describe();$('#job-action').addEventListener('change',describe);
 $('#job-form').addEventListener('submit',event=>{event.preventDefault(); const action=$('#job-action').value;startJob(action,['parse','verify'].includes(action)?$('#job-ids').value:'',$('#job-cache').checked);});
 displayJob();
}
async function startJob(action,cardIds='',cached=true) {
 try {
  state.job=await api('/api/jobs',{action,language:state.language,cardIds,cached});
  $('#card-dialog').close();navigate('jobs');displayJob();toast('Traitement démarré. Le journal se met à jour automatiquement.');
 } catch(e){toast(e.message,true);}
}
function displayJob() {
 const j=state.job; const running=j?.state==='running';
 $('#job-dot').className=running?'status-dot busy':'';
 updateWorkshopProgress();
 if(!$('#job-log'))return;
 $('#run-job').disabled=running;
 if(!j)return;
 const labels={running:'EN COURS',success:'TERMINÉ',error:'ÉCHEC'};
 $('#job-state').textContent=labels[j.state] || 'INTERROMPU';$('#job-state').className=`live-tag ${j.state}`;
 const seconds=Math.max(0,Math.round((j.finished || Date.now()/1000)-j.started));
 $('#job-summary').innerHTML=`<strong>${j.workshop?(j.stage==='verify'?'Vérifier la correction':'Appliquer la correction'):(actionLabels[j.action] || j.action)}</strong><span>${j.language.toUpperCase()} · ${Math.floor(seconds/60)} min ${seconds%60} s${j.exitCode!==null?` · code ${j.exitCode}`:''}</span>${running?'<div class="progress-track"><span></span></div>':''}`;
 const log=$('#job-log'), nearBottom=log.scrollHeight-log.scrollTop-log.clientHeight<70;
 log.textContent=j.lines.join('\n') || 'Initialisation du moteur…';if(nearBottom)log.scrollTop=log.scrollHeight;
}
async function pollJob() {
 try {
  const previous=state.job;
  state.job=await api('/api/job');
  displayJob();
  if(previous?.state==='running'&&state.job?.state!=='running'){
   const result=state.job?.workshopResult;
   toast(result?.message || (state.job.state==='success'?'Traitement terminé. Consultez le journal pour les détails.':'Le traitement a échoué. Consultez le journal.'), result?['failed','not_applied'].includes(result.status):state.job.state!=='success');
   state.reviewLanguage=null;
   await load();
   if(state.job.workshop)await refreshOpenCard();
  }
 } catch { /* Retry on the next poll; interactive requests report errors. */ }
}
async function renderExports() {
 $('#content').innerHTML=header('PRÊTES POUR LA SUITE','Vos données, à emporter.','Retrouvez les fichiers générés par LorcanaJSON.',`<button class="button" id="open-output">${icon('folder')}Ouvrir le dossier</button>`)+`<section class="panel"><div class="section-heading"><h2>Fichiers disponibles · ${state.language.toUpperCase()}</h2><span class="subtle-tag">SORTIE LOCALE</span></div><div id="export-list" class="loading">Lecture des exports…</div></section><div class="export-callout">${icon('box')}<div><h3>Besoin de données plus récentes ?</h3><p>Lancez une analyse pour régénérer vos fichiers JSON, XML et archives.</p></div><button class="button" data-page="jobs">Ouvrir les traitements ${icon('arrow')}</button></div>`;
 try { const lang=state.language;const files=await api(`/api/exports?language=${lang}`);if(state.page!=='exports'||state.language!==lang)return;const el=$('#export-list');el.className='export-list';el.innerHTML=files.map(f=>`<div class="export-row"><span class="file-icon">${icon(f.name.endsWith('.zip')?'box':'code')}</span><div><strong>${escapeHtml(f.name)}</strong><small>${date(f.modified*1000)} · ${size(f.size)}</small></div><a class="button" href="/export?language=${lang}&name=${encodeURIComponent(f.name)}&token=${encodeURIComponent(token)}" download>${icon('download')}Télécharger</a></div>`).join('')||empty('Aucun export pour cette langue','Lancez une première analyse depuis Traitements.');} catch(e){toast(e.message,true);}
}
async function renderSettings() {
 $('#content').innerHTML=header('SOUS LE CAPOT','Votre environnement.','Le studio s’appuie sur votre installation locale de LorcanaJSON.')+'<div id="settings-content" class="loading">Vérification de l’environnement…</div>';
 try{const d=await api('/api/diagnostics');if(state.page!=='settings')return;$('#settings-content').className='settings-grid';$('#settings-content').innerHTML=`<section class="panel"><div class="section-heading"><h2>Moteur Python</h2><span class="live-tag ${d.ready?'success':'error'}">${d.ready?'DISPONIBLE':'À CONFIGURER'}</span></div><label class="setting-label">Interpréteur utilisé<code>${escapeHtml(d.python)}</code></label><label class="setting-label">Dossier du projet<code>${escapeHtml(d.root)}</code></label>${d.ready?'<p class="muted">Les dépendances du moteur sont installées.</p>':`<div class="notice warning">${icon('info')}<span>Le catalogue et l’atelier fonctionnent. Pour lancer les traitements, installez les dépendances du moteur dans cet environnement.</span></div><p class="muted">Dépendances absentes :</p><div class="dependency-chips">${d.missing.map(m=>`<span>${escapeHtml(m)}</span>`).join('')}</div><p class="field-help">Consultez studio/README.md pour l’installation. Le lanceur utilise automatiquement .venv-studio s’il existe.</p>`}</section><section class="panel"><div class="section-heading"><h2>Les détails qui comptent</h2>${icon('shield')}</div><div class="setting-row"><span>Stockage des données<small>Catalogue, images et corrections</small></span><strong>Sur ce PC</strong></div><div class="setting-row"><span>Sauvegardes des corrections<small>.fred-studio/backups</small></span><strong>Automatiques</strong></div><div class="setting-row"><span>Modèle OCR français<small>fra.traineddata</small></span><strong>${d.models.fr?'Présent':'Absent'}</strong></div><div class="setting-row"><span>Modèle OCR anglais<small>eng.traineddata</small></span><strong>${d.models.en?'Présent':'Absent'}</strong></div><div class="notice">${icon('info')}<span>FRED Studio 0.1 · Interface locale. Les opérations de téléchargement contactent les services utilisés par LorcanaJSON.</span></div></section>`;}catch(e){toast(e.message,true);}
}

document.addEventListener('click',async event=>{
 const button=event.target.closest('button,a.brand');if(!button)return;
 if(button.matches('a.brand')){event.preventDefault();navigate('home');}
 if(button.dataset.page)navigate(button.dataset.page);
 if(button.dataset.card){state.workshopMode='suggestions';openCard(Number(button.dataset.card),state.page==='corrections'?'edit':'data');}
 if(button.dataset.tab)renderDetail(button.dataset.tab);
 if(button.hasAttribute('data-close')){$('#card-dialog').close();detailSequence++;}
 if(button.hasAttribute('data-reload'))load();
 if(button.dataset.action)startJob(button.dataset.action,button.dataset.ids || '');
 if(button.dataset.view){state.view=button.dataset.view;renderCatalog();}
 if(button.id==='load-more'){state.limit+=48;updateResults();}
 if(button.id==='reset-filters'){Object.assign(state,{search:'',set:'',color:'',rarity:'',limit:48});renderCatalog();}
 if(button.id==='save-correction')saveCorrection(button);
 if(button.id==='copy-json'){try{await navigator.clipboard.writeText(JSON.stringify(state.selected.card,null,2));toast('JSON copié.');}catch{toast('Copie indisponible : sélectionnez le texte JSON.',true);}}
 if(button.id==='open-output'){try{await api('/api/open-output',{language:state.language});}catch(e){toast(e.message,true);}}
});
$('#language').value=state.language;
$('#language').addEventListener('change',event=>{state.language=event.target.value;localStorage.setItem('fred-language',state.language);state.set='';state.color='';state.rarity='';$('#card-dialog').close();load();});
$('#refresh').addEventListener('click',()=>load());
$('#card-dialog').addEventListener('click',event=>{if(event.target===$('#card-dialog')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();if($('#card-dialog').open)return;navigate('catalog');$('#search').focus();}});
$$('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));
load();pollJob();setInterval(pollJob,2000);
