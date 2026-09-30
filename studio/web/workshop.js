/* Workshop UI: source-backed proposals, direct editing, history and reprocessing. */
const historyLabels = {
  queued: 'En attente', running: 'Application en cours', verified: 'Appliquée et vérifiée',
  applied: 'Appliquée · à relire', failed: 'Traitement en échec', not_applied: 'Résultat à relire',
  interrupted: 'Traitement interrompu', undone: 'Annulée'
};
state.workshopMode = 'suggestions';
state.reviewScope = 'review';
state.review = null;
state.reviewLanguage = null;
state.drafts = new Map();

function diffMarkup(diff) {
  const side = (key, label) => `<div class="diff-side ${key}"><div class="diff-label">${key==='before'?'−':'+'} ${label}</div><div class="diff-text">${diff[key].map(part => part.changed ? `<mark>${escapeHtml(part.text)}</mark>` : escapeHtml(part.text)).join('') || '<span class="muted">Texte supprimé</span>'}</div></div>`;
  return `<div class="diff-comparison">${side('before','Texte actuel')}${side('after','Correction proposée')}</div>`;
}

function workshopRunning() {
  return state.applying || state.job?.state === 'running';
}

function renderWorkshop(panel) {
  const report = state.selected.workshop;
  if (!report) {
    panel.innerHTML = `<div class="notice warning">${icon('info')}La nouvelle version du moteur n’est pas encore chargée. Relancez FRED Studio.</div>`;
    return;
  }
  const count = report.proposals.filter(p=>p.actionable).length;
  const mode = state.workshopMode || 'suggestions';
  panel.innerHTML = `<div class="workshop-intro"><span class="workshop-spark">${icon('spark')}</span><div><h3>Un regard de plus sur chaque détail.</h3><p>${count ? `${count} proposition${count>1?'s':''} prête${count>1?'s':''} à appliquer.` : 'Comparaison avec les références locales du projet.'}</p></div></div>
    <div class="workshop-nav" aria-label="Outils de correction">
      <button data-workshop-mode="suggestions" class="${mode==='suggestions'?'active':''}">Suggestions <span>${report.proposals.length}</span></button>
      <button data-workshop-mode="editor" class="${mode==='editor'?'active':''}">Modifier</button>
      <button data-workshop-mode="history" class="${mode==='history'?'active':''}">Historique <span>${state.selected.history.length}</span></button>
      <button data-workshop-mode="advanced" class="${mode==='advanced'?'active':''}">Avancé</button>
    </div><div id="workshop-progress" aria-live="polite"></div><div id="workshop-body"></div>`;
  const body = $('#workshop-body');
  if (mode === 'suggestions') {
    body.innerHTML = `<div class="diff-legend"><span class="legend-before">− Passage à relire</span><span class="legend-after">+ Proposition</span><span>À comparer avec l’image</span></div>`;
    if (!report.proposals.length && !report.notes.length) {
      body.insertAdjacentHTML('beforeend', `<div class="workshop-clear">${icon('check')}<h3>Aucun écart détecté</h3><p>Les champs comparés concordent avec la référence locale. Vous pouvez toujours modifier un champ manuellement.</p><button class="button" data-workshop-mode="editor">${icon('edit')}Modifier un champ</button></div>`);
    }
    body.insertAdjacentHTML('beforeend', report.proposals.map(p=>`<article class="suggestion-card"><div class="suggestion-heading"><strong>${escapeHtml(p.label)}</strong><span class="confidence ${p.actionable?'reference':'review'}">${p.actionable?'Référence disponible':'À relire'}</span></div><p class="suggestion-reason">${escapeHtml(p.reason)}</p>${diffMarkup(p.diff)}<div class="suggestion-footer"><span>${icon('shield')}${escapeHtml(p.source)}</span>${p.actionable?`<button class="button primary" data-apply-proposal="${p.key}" ${workshopRunning()?'disabled':''}>${icon('check')}Appliquer et vérifier</button>`:`<button class="button" data-edit-path="${escapeHtml(p.path)}">${icon('edit')}Relire dans l’éditeur</button>`}</div></article>`).join(''));
    body.insertAdjacentHTML('beforeend', report.notes.map(n=>`<article class="review-note"><h4>${icon('info')}${escapeHtml(n.label)}</h4><p>${escapeHtml(n.reason)}</p>${n.diff?`<details><summary>Comparer les textes</summary>${diffMarkup(n.diff)}</details>`:''}</article>`).join(''));
  }
  if (mode === 'editor') renderDirectEditor(body);
  if (mode === 'history') renderWorkshopHistory(body);
  if (mode === 'advanced') renderAdvancedEditor(body);
  updateWorkshopProgress();
}

function renderDirectEditor(body) {
  const fields = state.selected.workshop.fields;
  if (!fields.length) { body.innerHTML = empty('Aucun champ modifiable','Cette carte ne contient pas de champ pris en charge.'); return; }
  const selected = fields.find(f=>f.path===state.editPath) || fields[0];
  state.editPath = selected.path;
  const draftKey = `${state.language}/${state.selected.card.id}/${selected.path}`;
  const draft = state.drafts.get(draftKey) ?? selected.value;
  body.innerHTML = `<form id="direct-edit-form"><label>Champ de la carte<select id="direct-field">${fields.map(f=>`<option value="${escapeHtml(f.path)}" ${f.path===selected.path?'selected':''}>${escapeHtml(f.label)}</option>`).join('')}</select></label><div class="direct-original"><div class="diff-label">Valeur actuelle</div><p>${escapeHtml(selected.value)}</p></div><label>Votre correction${selected.numeric?`<input id="direct-value" type="number" min="0" max="99" step="1" value="${draft}">`:`<textarea id="direct-value" rows="5">${escapeHtml(draft)}</textarea>`}</label><div class="form-actions"><button type="submit" class="button">Prévisualiser</button><button type="button" id="apply-direct" class="button primary" disabled>${icon('check')}Appliquer et vérifier</button></div><div id="direct-preview" aria-live="polite"></div></form><p class="field-help direct-help">La règle est sauvegardée, puis la carte et ses exports sont régénérés. Votre brouillon reste disponible pendant la navigation entre les cartes.</p>`;
  $('#direct-field').addEventListener('change',event=>{state.editPath=event.target.value;renderDirectEditor(body);});
  $('#direct-value').addEventListener('input',event=>{state.drafts.set(draftKey,event.target.value);state.directPreview=null;$('#apply-direct').disabled=true;$('#direct-preview').innerHTML='';});
  $('#direct-edit-form').addEventListener('submit', async event=>{
    event.preventDefault();
    const payload = directPayload();
    try {
      const preview = await api('/api/workshop/preview',payload);
      if (!$('#direct-preview') || JSON.stringify(payload)!==JSON.stringify(directPayload())) return;
      state.directPreview=JSON.stringify(payload);
      $('#direct-preview').innerHTML=diffMarkup(preview.diff);
      $('#apply-direct').disabled=workshopRunning();
    } catch(e) { toast(e.message,true); }
  });
}

function directPayload() {
  const field=state.selected.workshop.fields.find(f=>f.path===$('#direct-field')?.value);
  const value=$('#direct-value')?.value;
  return {language:state.language,id:state.selected.card.id,fingerprint:state.selected.workshop.fingerprint,path:field?.path,after:field?.numeric?Number(value):value};
}

function renderWorkshopHistory(body) {
  const entries=state.selected.history;
  if (!entries.length) {body.innerHTML=empty('L’historique commence ici','Les corrections appliquées depuis cet atelier apparaîtront ici, avec leur résultat de vérification.');return;}
  body.innerHTML=entries.map((entry,index)=>`<article class="history-entry"><div class="suggestion-heading"><strong>${entry.undoOf?'Annulation · ':''}${escapeHtml(entry.label)}</strong><span class="history-status ${entry.status}">${historyLabels[entry.status] || escapeHtml(entry.status)}</span></div><p class="history-date">${new Date(entry.created*1000).toLocaleString('fr-FR')}</p>${entry.message?`<p class="suggestion-reason">${escapeHtml(entry.message)}</p>`:''}<details><summary>Voir la modification</summary><div class="diff-comparison"><div class="diff-side before"><div class="diff-label">− Avant</div><div class="diff-text">${escapeHtml(entry.before)}</div></div><div class="diff-side after"><div class="diff-label">+ Après</div><div class="diff-text">${escapeHtml(entry.after)}</div></div></div></details><div class="history-actions">${['failed','not_applied','interrupted'].includes(entry.status)?`<button class="button" data-retry-entry="${entry.key}" ${workshopRunning()?'disabled':''}>${icon('refresh')}Réessayer</button>`:''}${!entry.undoOf&&entry.status!=='undone'&&entry.status!=='running'?`<button class="text-button" data-undo-entry="${entry.key}" ${workshopRunning()?'disabled':''}>${icon('refresh')}Annuler cette correction</button>`:''}</div></article>`).join('');
}

function updateWorkshopProgress() {
  const banner=$('#workshop-progress');
  if (!banner) return;
  const job=state.job;
  const active=job?.workshop && job.language===state.language && state.selected.history.some(h=>h.key===job.workshop);
  if (active && job.state==='running') {
    banner.innerHTML=`<div class="workshop-progress"><span class="spinner"></span><div><strong>${job.stage==='verify'?'Vérification de la carte…':'Application de la correction…'}</strong><p>${job.stage==='verify'?'Comparaison du résultat avec les références.':'La carte et les fichiers de sortie sont régénérés.'}</p></div><button class="text-button" data-open-journal>Voir le journal</button></div>`;
  } else if (active && job.workshopResult) {
    const result=job.workshopResult;
    banner.innerHTML=`<div class="workshop-outcome ${result.status}">${icon(result.status==='verified'?'check':'info')}<span>${escapeHtml(result.message)}</span><button class="text-button" data-open-journal>Journal</button></div>`;
  } else { banner.innerHTML=''; }
  $$('[data-apply-proposal],[data-undo-entry],[data-retry-entry]').forEach(button=>button.disabled=workshopRunning());
}

async function applyWorkshop(payload, endpoint='/api/workshop/apply') {
  if (workshopRunning()) return;
  state.applying=true; updateWorkshopProgress();
  const cardId=state.selected.card.id;
  const lang=state.language;
  try {
    const result=await api(endpoint,payload);
    state.job=result.job;
    state.drafts.delete(`${lang}/${cardId}/${payload.path}`);
    const detail=await api(`/api/card?language=${lang}&id=${cardId}`);
    if ($('#card-dialog').open && state.selected.card.id===cardId && state.language===lang) {
      state.selected=detail;
      state.workshopMode='history';
      renderDetail('edit');
    }
    toast('Correction enregistrée. Application et vérification en cours.');
  } catch(e) {toast(e.message,true);}
  finally {state.applying=false;updateWorkshopProgress();}
}

async function refreshOpenCard() {
  if (!$('#card-dialog').open || !state.selected) return;
  const id=state.selected.card.id, lang=state.language, seq=++detailSequence;
  const detail=await api(`/api/card?language=${lang}&id=${id}`);
  if (seq!==detailSequence || !$('#card-dialog').open || state.language!==lang) return;
  state.selected=detail;
  renderDetail(state.detailTab || 'data');
}

async function loadReview() {
  const lang=state.language;
  if (state.reviewLoading===lang) return;
  state.reviewLoading=lang;
  try {
    const rows=await api(`/api/workshop/review?language=${lang}`);
    if (state.language!==lang) return;
    state.review=new Map(rows.map(r=>[r.id,r]));state.reviewLanguage=lang;
    if (state.page==='corrections') updateResults();
  } catch(e) {toast(e.message,true);if($('#catalog-results')&&state.page==='corrections')$('#catalog-results').innerHTML=empty('Comparaison indisponible',escapeHtml(e.message));}
  finally {if(state.reviewLoading===lang)state.reviewLoading=null;}
}

function navigateCard(direction) {
  const ids=state.visibleIds?.includes(state.selected.card.id)?state.visibleIds:cardsSorted().map(c=>c.id);
  const index=ids.indexOf(state.selected.card.id);
  const target=ids[index+direction];
  if(target!==undefined)openCard(target,state.detailTab || 'data');
}

document.addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.workshopMode){state.workshopMode=button.dataset.workshopMode;renderWorkshop($('#detail-tab'));}
  if(button.dataset.editPath){state.editPath=button.dataset.editPath;state.workshopMode='editor';renderWorkshop($('#detail-tab'));}
  if(button.dataset.applyProposal)applyWorkshop({language:state.language,id:state.selected.card.id,fingerprint:state.selected.workshop.fingerprint,proposal:button.dataset.applyProposal});
  if(button.id==='apply-direct'){
    const payload=directPayload();
    if(JSON.stringify(payload)===state.directPreview)applyWorkshop(payload);
  }
  if(button.dataset.undoEntry)applyWorkshop({language:state.language,entry:button.dataset.undoEntry},'/api/workshop/undo');
  if(button.dataset.retryEntry)applyWorkshop({language:state.language,entry:button.dataset.retryEntry},'/api/workshop/retry');
  if(button.hasAttribute('data-open-journal')){$('#card-dialog').close();navigate('jobs');}
  if(button.dataset.reviewScope){state.reviewScope=button.dataset.reviewScope;renderCatalog();}
  if(button.dataset.cardDirection)navigateCard(Number(button.dataset.cardDirection));
  if(button.hasAttribute('data-zoom')){
    const el=$('.detail-visual');el.classList.toggle('zoomed');
    button.setAttribute('aria-pressed',String(el.classList.contains('zoomed')));
    button.title=el.classList.contains('zoomed')?'Réduire l’image':'Agrandir l’image';
  }
});
document.addEventListener('keydown',event=>{
  if(!$('#card-dialog').open || !state.selected || event.target.closest('input,textarea,select,[contenteditable]'))return;
  if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();navigateCard(event.key==='ArrowRight'?1:-1);}
});
