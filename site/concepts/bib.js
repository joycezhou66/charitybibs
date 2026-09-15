/* charitybibs concepts — shared data helpers and the "back of the bib" renderer. */
window.CB = (function(){
  const DATA = window.CB_DATA;
  const all = DATA.charities;
  const money = n => n==null ? '—' : '$' + n.toLocaleString('en-US');
  const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const fmt = iso => { if(!iso) return null; const [y,m,d]=iso.split('-'); return MON[+m-1]+' '+(+d)+', '+y; };
  const REG = 315; // NYRR entry, non-member, as cited on charity pages; members $255
  const SUP = [["coaching","A coach"],["group_runs","Group runs"],["training_plan","A training plan"],["fundraising_coaching","Help fundraising"],["team_events","Team events"],["gear","Gear"],["fundraising_page","A fundraising page"],["bus_to_start","A bus to the start"],["charity_village","A tent at the start"],["hotel_or_travel","Hotel help"]];
  const TRAIN = ["coaching","group_runs","training_plan"], FUND = ["fundraising_coaching","fundraising_page","team_events"];
  const STATUS = {open:['Taking runners','Applications are open'], waitlist:['Waitlist','Full for 2026, waitlist open'], closed:['Closed','Not taking runners for 2026'], unknown:['Not sure','They don\'t say']};
  const statusRank = s => ({open:0,waitlist:1,unknown:2,closed:3}[s] ?? 3);
  const termsCount = c => (c.shortfall&&c.shortfall.pub?1:0)+(c.injury&&c.injury.pub?1:0)+(c.deferral&&c.deferral.pub?1:0)+(c.freeExit?1:0);
  const lit = c => SUP.filter(([k])=>c.support[k]===true);
  const label = k => SUP.find(([kk])=>kk===k)[1];
  const list = arr => arr.length<=1 ? arr.join('') : arr.slice(0,-1).join(', ')+' and '+arr[arr.length-1];
  const lower = s => s.charAt(0).toLowerCase()+s.slice(1);
  // "A coach, group runs and a training plan." or "Not described on their page."
  const helpSentence = c => { const l = lit(c).map(([,v])=>lower(v)); return l.length ? l.join(', ').replace(/^./,ch=>ch.toUpperCase()) : ''; };
  const due = c => c.deadline && c.deadline>='2026-01-01' ? fmt(c.deadline) : null;
  const total = c => (c.min||0) + (c.regSeparate===false?0:REG) + (c.fee&&c.feeCreditable===false?c.fee:0);

  const q = (title, o, extra) => '<section class="bk q"><h4>'+title+'</h4>'+
    (o.pub ? '<p>'+esc(o.text)+'</p>'+(o.quote?'<blockquote>“'+esc(o.quote)+'”</blockquote>':'')+(o.source?'<a class="src" href="'+esc(o.source)+'" target="_blank" rel="noopener">Read it on their page ↗</a>':'')
           : '<p class="np">They don\'t say. Ask before you sign up.</p>')+
    (extra?'<p class="fine">'+extra+'</p>':'')+'</section>';

  function back(c){
    const [sWord,sLine]=STATUS[c.status];
    const reg = c.regSeparate===false ? '<div><span>NYRR race entry</span><span>covered</span></div>' : '<div><span>NYRR entry fee</span><span>+ '+money(REG)+'</span></div>';
    const feeLabel = (c.feeLabel||'Charity fee').split(',')[0]; const feeShort = feeLabel.length>28 ? 'Charity fee' : feeLabel;
    const fee = c.fee ? '<div><span>'+esc(feeShort)+(c.feeCreditable===false?' (doesn\'t count)':c.feeCreditable===true?' (counts toward your total)':' (they don\'t say if it counts)')+'</span><span>'+(c.feeCreditable===false?'+ '+money(c.fee):'('+money(c.fee)+')')+'</span></div>' : '';
    const help = '<ul class="help">'+SUP.map(([k,l])=>'<li class="'+(c.support[k]===true?'':'off')+'">'+l+'</li>').join('')+'</ul>';
    const freeExit = c.freeExit ? {pub:true, text:'You can back out for free until '+fmt(c.freeExit)+'.', quote:c.freeExitQuote, source:c.minSource||c.url} : {pub:false};
    return '<div class="back" id="back-'+esc(c.id)+'">'+
      '<div class="back-h"><span class="lab">Back of the bib · '+esc(c.name)+'</span><span class="lab">Read from their pages on '+fmt(c.verified)+'</span></div>'+
      '<div class="back-grid">'+
      '<section class="bk"><h4>How much do I raise?</h4><p class="big">'+money(c.min)+' for the charity'+(due(c)?', due '+due(c):'')+'.</p>'+
        '<div class="receipt"><div><span>You raise for the charity</span><span>'+money(c.min)+'</span></div>'+reg+fee+'<div class="tot"><span>Most you could be out if you raised nothing</span><span>'+money(total(c))+'</span></div></div>'+
        '<p class="fine">NYRR entry is $255 for NYRR members.'+(c.minNote?' '+esc(c.minNote):'')+'</p>'+
        (c.minSource?'<a class="src" href="'+esc(c.minSource)+'" target="_blank" rel="noopener">Read it on their page ↗</a>':'')+'</section>'+
      '<section class="bk"><h4>What do they give me?</h4>'+help+(c.supportNotes?'<p class="fine" style="margin-top:8px">'+esc(c.supportNotes)+'</p>':'')+(c.supportSource?'<a class="src" href="'+esc(c.supportSource)+'" target="_blank" rel="noopener">Read it on their page ↗</a>':'')+'</section>'+
      '<section class="bk"><h4>Are they still taking runners?</h4><p><span class="st '+c.status+'">'+sWord+'</span></p><p>'+sLine+(c.spots?'. '+esc(c.spots):'')+'.</p>'+(due(c)?'<p class="fine">Money is due by '+due(c)+'.</p>':'')+'</section>'+
      q('What if I don\'t raise it all?', c.shortfall, c.chargeSchedule?'When they take the money: '+esc(c.chargeSchedule):'')+
      q('What if I get hurt and can\'t run?', c.injury, '')+
      q('Can I move my spot to next year?', c.deferral, '')+
      q('Until when can I back out for free?', freeExit, '')+
      '</div>'+
      '<div class="back-go"><a class="btn print" href="'+esc(c.url)+'" target="_blank" rel="noopener">Go to '+esc(c.name.split(' (')[0])+'\'s marathon page ↗</a><a class="btn" href="mailto:hello@charitybibs.com?subject=Correction%3A%20'+encodeURIComponent(c.name)+'">Something wrong here?</a>'+(c.level?'<span class="lab">NYRR '+esc(c.level)+' partner</span>':'')+'</div>'+
    '</div>';
  }
  const causes = [...new Set(all.map(c=>c.cause).filter(Boolean))].sort((a,b)=>all.filter(c=>c.cause===b).length-all.filter(c=>c.cause===a).length || a.localeCompare(b));
  return {DATA, all, money, esc, fmt, REG, SUP, TRAIN, FUND, STATUS, statusRank, termsCount, lit, label, list, helpSentence, due, total, back, causes,
    download(){ const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(DATA,null,2)],{type:'application/json'}));a.download='charitybibs-nyc-2026.json';a.click(); }};
})();
