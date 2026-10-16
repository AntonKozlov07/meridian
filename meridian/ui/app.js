/* Step 2: static mock data. Later steps replace T/hist/userQ/ctxQ with state pushed from Python. */
(function(){
var LIVE=!!window.pywebview;
if(!LIVE)window.addEventListener('pywebviewready',function(){location.reload();});
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
var S='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">';
var F='<svg viewBox="0 0 24 24" fill="currentColor">';
var I={
  play:F+'<path d="M8 5.6v12.8a1.2 1.2 0 0 0 1.8 1l10-6.4a1.2 1.2 0 0 0 0-2l-10-6.4A1.2 1.2 0 0 0 8 5.6z"/></svg>',
  pause:F+'<rect x="6" y="5" width="4.2" height="14" rx="1.4"/><rect x="13.8" y="5" width="4.2" height="14" rx="1.4"/></svg>',
  prev:F+'<rect x="4.5" y="5" width="2.4" height="14" rx="1.2"/><path d="M19.5 6.3v11.4a1 1 0 0 1-1.6.8L9.7 12.8a1 1 0 0 1 0-1.6l8.2-5.7a1 1 0 0 1 1.6.8z"/></svg>',
  next:F+'<rect x="17.1" y="5" width="2.4" height="14" rx="1.2"/><path d="M4.5 6.3v11.4a1 1 0 0 0 1.6.8l8.2-5.7a1 1 0 0 0 0-1.6L6.1 5.5a1 1 0 0 0-1.6.8z"/></svg>',
  shuffle:S+'<path d="M16 4h4v4M4 20 20 4M20 16v4h-4M14.5 14.5 20 20M4 4l5 5"/></svg>',
  repeat:S+'<path d="m17 2 3 3-3 3"/><path d="M4 11v-1a5 5 0 0 1 5-5h11M7 22l-3-3 3-3"/><path d="M20 13v1a5 5 0 0 1-5 5H4"/></svg>',
  heart:S+'<path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 1 1 12 6a5 5 0 1 1 7.5 6.6z"/></svg>',
  heartF:'<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round"><path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 1 1 12 6a5 5 0 1 1 7.5 6.6z"/></svg>',
  plus:S+'<path d="M12 5v14M5 12h14"/></svg>',
  share:S+'<path d="M12 3v12M8 7l4-4 4 4M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>',
  more:F+'<circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/></svg>',
  vol:S+'<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/></svg>',
  mute:S+'<path d="M11 5 6 9H3v6h3l5 4z"/><path d="m22 9-6 6M16 9l6 6"/></svg>',
  devices:S+'<rect x="3" y="4" width="13" height="10" rx="2"/><path d="M7 20h5"/><rect x="18" y="8" width="4" height="12" rx="1.5"/></svg>',
  laptop:S+'<rect x="4" y="5" width="16" height="10" rx="2"/><path d="M2 19h20"/></svg>',
  speaker:S+'<rect x="5" y="2.5" width="14" height="19" rx="3"/><circle cx="12" cy="14" r="3.5"/><path d="M12 6.5h.01"/></svg>',
  phone:S+'<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18h2"/></svg>',
  search:S+'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  home:S+'<path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5H15v-6H9v6H5.5A1.5 1.5 0 0 1 4 19z"/></svg>',
  compass:S+'<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/></svg>',
  radio:S+'<path d="M5 12a7 7 0 0 1 14 0M8.5 12a3.5 3.5 0 0 1 7 0"/><circle cx="12" cy="12" r="1"/><path d="M12 13v7"/></svg>',
  back:S+'<path d="m15 6-6 6 6 6"/></svg>',
  fwd:S+'<path d="m9 6 6 6-6 6"/></svg>',
  chev:S+'<path d="m7 10 5 5 5-5"/></svg>',
  expand:S+'<path d="M15 4h5v5M9 20H4v-5M20 4l-6 6M4 20l6-6"/></svg>',
  lyrics:S+'<path d="M4 6h16M4 10.5h16M4 15h10M4 19.5h6"/></svg>',
  sliders:S+'<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></svg>',
  x:S+'<path d="M6 6l12 12M18 6 6 18"/></svg>'
};
var PAL=[["#2b211c","#c7672f","#efe4d2"],["#e9e1d3","#2b2723","#b8892e"],["#3a2a22","#d9a55a","#8a3b2a"],["#1f2420","#8c9a6b","#e7dcc6"],["#c4a57a","#3b2c24","#f1e8da"],["#5b2a22","#e3b868","#1d1a17"],["#d8cfc0","#7c5a3a","#2a2522"],["#262320","#cf8a45","#9aa07a"],["#8a3b2a","#efe4d2","#2b211c"],["#3b3a2c","#d9a55a","#c7672f"]];
function artT(i){var x=T[i];return x&&x.img?'<img src="'+esc(x.img)+'" alt="" style="width:100%;height:100%;object-fit:cover;display:block">':art(i);}
function art(i){
  var p=PAL[i%PAL.length],g=p[0],a=p[1],b=p[2],k=i%5,s='';
  if(k===0)s='<circle cx="64" cy="36" r="24" fill="'+a+'"/><rect x="0" y="66" width="100" height="34" fill="'+b+'"/><rect x="12" y="66" width="22" height="34" fill="'+a+'"/>';
  if(k===1)s='<rect x="14" y="14" width="72" height="72" fill="none" stroke="'+a+'" stroke-width="2"/><path d="M14 86A72 72 0 0 1 86 14V86z" fill="'+b+'"/>';
  if(k===2){for(var j=0;j<6;j++)s+='<rect x="0" y="'+(j*16+4)+'" width="100" height="7" fill="'+(j%2?a:b)+'"/>';s+='<circle cx="30" cy="50" r="18" fill="'+g+'"/>';}
  if(k===3)s='<path d="M0 100A50 50 0 0 1 50 50V100z" fill="'+a+'"/><path d="M50 50A50 50 0 0 1 100 0V50z" fill="'+b+'"/><rect x="50" y="50" width="50" height="50" fill="'+b+'"/><circle cx="75" cy="75" r="14" fill="'+a+'"/>';
  if(k===4)s='<rect x="20" y="0" width="22" height="100" fill="'+a+'"/><rect x="58" y="30" width="42" height="42" fill="'+b+'"/><rect x="0" y="80" width="100" height="2" fill="'+b+'"/>';
  return '<svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice"><rect width="100" height="100" fill="'+g+'"/>'+s+'</svg>';
}
var T=[
 {en:72,pc:23,t:"Low Tide Arithmetic",a:"Hollis Marr",al:"Field Recordings Vol. II",y:2024,d:252,bpm:118,key:"F♯ minor",lufs:"−8.2",
  ly:[[0,"♪"],[14,"Counting the boats that never came in"],[22,"Writing the sums on the back of my hand"],[31,"Every wave a number I forget"],[40,"Every number something I don't understand"],[52,"And the harbour lights go out in order"],[60,"One, then two, then all of them at once"],[70,"I keep the change the water gives me"],[79,"Small and cold and worth about as much"],[94,"♪"],[118,"Low tide, low tide"],[126,"Show me what you took and what you kept"],[136,"Low tide, low tide"],[144,"I can do the math, I just can't do it yet"]],
  cr:[["Performed by",["Hollis Marr","Vocals, guitar"],["Ada Pruett","Drums"]],["Written by",["Hollis Marr"],["Teo Lindqvist"]],["Produced by",["Teo Lindqvist"]],["Mixed by",["Rhea Okafor"]],["Mastered by",["Ben Castell","Halfmoon Mastering"]],["Label",["Tideline Records"]]]},
 {en:58,pc:9,t:"Concrete Orchard",a:"Ines Varga",al:"Concrete Orchard",y:2023,d:227,bpm:96,key:"D major",lufs:"−9.6",
  ly:[[0,"Grew a tree out of the parking lot"],[9,"Watered it with everything I had"],[18,"Nobody asked me what it was for"],[27,"Nobody stopped to tell me it was bad"],[38,"Fruit like rivets, leaves like tin"],[46,"Let the whole grey city in"]],
  cr:[["Performed by",["Ines Varga"]],["Written by",["Ines Varga"]],["Produced by",["Marco Ilic"]],["Label",["Self-released"]]]},
 {en:41,pc:4,t:"Night Shift at the Foundry",a:"The Quiet Ledger",al:"Overtime",y:2022,d:303,bpm:84,key:"A minor",lufs:"−10.1"},
 {en:63,pc:12,t:"Paper Lanterns, Late",a:"Okoro & Wren",al:"Two Rooms",y:2025,d:209,bpm:102,key:"E♭ major",lufs:"−8.9"},
 {en:81,pc:31,t:"Tungsten",a:"Mira Solberg",al:"Filament",y:2024,d:281,bpm:124,key:"C minor",lufs:"−7.4"},
 {en:47,pc:2,t:"Halfway Houses",a:"Dalton Reyes",al:"Rest Stops",y:2021,d:238,bpm:90,key:"G major",lufs:"−9.2"},
 {en:88,pc:17,t:"Ember Count",a:"Hollis Marr",al:"Field Recordings Vol. II",y:2024,d:174,bpm:132,key:"B minor",lufs:"−8.0"},
 {en:66,pc:6,t:"Northbound Static",a:"Ines Varga",al:"Concrete Orchard",y:2023,d:260,bpm:110,key:"F major",lufs:"−9.0"},
 {en:35,pc:1,t:"Copper Wire Hymn",a:"Ada Pruett",al:"Conductors",y:2025,d:196,bpm:76,key:"D minor",lufs:"−11.3"},
 {en:52,pc:0,t:"Last Ferry Out",a:"The Quiet Ledger",al:"Overtime",y:2022,d:322,bpm:88,key:"E minor",lufs:"−9.8",off:true}
];
var PLS=[["Late Hours","Playlist · 48 songs",2],["Liked Songs","Playlist · 1,284 songs",5],["Workshop Focus","Playlist · 112 songs",3],["Field Recordings Vol. II","Album · Hollis Marr",0],["Sunday Records","Playlist · 31 songs",4],["Road North","Playlist · 67 songs",7],["Overtime","Album · The Quiet Ledger",2],["Archive 2019–2023","Playlist · 406 songs",8],["Filament","Album · Mira Solberg",4]];
var DEV=[["laptop","This computer","Web player"],["speaker","Living Room","Spotify Connect · Wi-Fi"],["phone","Anton's Phone","Spotify Connect"],["speaker","Studio Monitors","Offline · last seen 2 days ago",1]];
function fmt(s){s=Math.max(0,Math.floor(s));return Math.floor(s/60)+":"+("0"+s%60).slice(-2);}
function hexA(h,a){var n=parseInt(h.slice(1),16);return 'rgba('+(n>>16&255)+','+(n>>8&255)+','+(n&255)+','+a+')';}
var hist=[2,6],userQ=[3],ctxQ=[4,5,7,8,9,1];
var st={cur:0,t:74,playing:true,vol:.72,muted:false,shuffle:false,repeat:0,liked:{0:true,4:true},tab:"lyrics",view:"listen",dev:0,ctx:"Late Hours"};
var PPS=1.5,CX=720,BASE=new Date(2026,9,15,21,41,0).getTime(),real0=Date.now(),clock0=0,seq=[];
function nowMs(){return LIVE?Date.now():BASE+(Date.now()-real0);}
function clk(ms){var d=new Date(ms),h=d.getHours(),m=d.getMinutes();return ((h%12)||12)+':'+('0'+m).slice(-2)+' '+(h<12?'AM':'PM');}
function eqg(){return '<span class="eqg'+(st.playing?'':' paused')+'"><i></i><i></i><i></i><i></i></span>';}
var app=document.getElementById('app');
app.innerHTML=
'<div class="amb" id="amb"></div>'+
'<header class="bar"><div class="bl"><div class="brand"><span class="mk"></span>Meridian</div><nav class="views" id="views"><button data-v="listen">Listen</button><button data-v="library">Library</button></nav></div>'+
  '<button class="cmd" id="cmdb">'+I.search+'<span>Search, or jump to anything</span><kbd>⌘K</kbd></button>'+
  '<div class="br"><span class="chip"><span class="dot"></span>Spotify</span><button class="btn" id="devb"></button><span class="av">AK</span></div></header>'+
'<section class="main" id="listen">'+
  '<div class="cover" id="cover"></div>'+
  '<div class="info"><div class="np" id="np"></div><div class="ttl" id="ttl"></div><div class="who" id="who"></div><div class="chips" id="chips"></div>'+
    '<div class="acts"><button class="ibtn soft" id="like" title="Save"></button><button class="ibtn soft" title="Add to playlist">'+I.plus+'</button><button class="ibtn soft" title="Share">'+I.share+'</button><button class="ibtn soft" title="More">'+I.more+'</button></div></div>'+
  '<div class="read"><div class="seg" id="tabs"><button data-t="lyrics">Lyrics</button><button data-t="credits">Credits</button><button data-t="about">About</button></div><div class="rpane" id="pane"></div></div>'+
'</section>'+
'<section class="main lib" id="library" hidden></section>'+
'<div class="ctrl"><div class="cl"><b id="el"></b><span id="ends"></span></div>'+
  '<div class="cc"><button class="ibtn" id="shuf" title="Shuffle (S)">'+I.shuffle+'</button><button class="ibtn" id="prev" title="Previous">'+I.prev+'</button><button class="pbtn lg" id="pp" title="Play / pause (Space)"></button><button class="ibtn" id="next" title="Next">'+I.next+'</button><button class="ibtn" id="rep" title="Repeat (R)">'+I.repeat+'<span class="badge" id="repb"></span></button></div>'+
  '<div class="cr"><span class="sub" id="upn"></span><button class="ibtn" id="mute"></button><div class="sld vol" id="vol"><div class="tr"><div class="fl"></div><div class="th"></div></div></div></div></div>'+
'<div class="tl" id="tl"><div class="strip" id="strip"></div><div class="noon"><span id="nowl"></span></div><div class="fade-l"></div><div class="fade-r"></div></div>'+
'<div class="pop" id="pop" style="width:300px"></div>'+
'<div class="pal" id="pal"><div class="box"><div class="in">'+I.search+'<input id="q" placeholder="Songs, artists, playlists, or a lyric"><kbd>esc</kbd></div><div class="res" id="res"></div><div class="ft"><span>↵ Play now</span><span>⇧↵ Add to queue</span><span>↑↓ Move</span></div></div></div>';
var $=function(id){return document.getElementById(id);};

function buildSeq(){
  if(LIVE){seq=liveSeq;return;}
  seq=[];var s=0;
  hist.forEach(function(i){seq.push({i:i,s:s,k:'past'});s+=T[i].d;});
  seq.push({i:st.cur,s:s,k:'cur'});s+=T[st.cur].d;
  userQ.forEach(function(i){seq.push({i:i,s:s,k:'mine'});s+=T[i].d;});
  ctxQ.forEach(function(i){seq.push({i:i,s:s,k:'next'});s+=T[i].d;});
}
function curS(){for(var k=0;k<seq.length;k++)if(seq[k].k==='cur')return seq[k].s;return 0;}
function nUpCount(){return seq.filter(function(b){return b.k!=='past'&&b.k!=='cur';}).length;}
function renderStrip(){
  buildSeq();clock0=nowMs()-(curS()+st.t)*1000;
  var h='';
  seq.forEach(function(b,k){var x=T[b.i],w=x.d*PPS-6;
    var sub=b.k==='past'?esc(x.a):b.k==='cur'?esc(x.a):esc(x.a)+' · <span class="mono">'+clk(clock0+b.s*1000)+'</span>';
    h+='<div class="blk '+b.k+(x.off?' off':'')+'" data-k="'+k+'" style="left:'+(b.s*PPS)+'px;width:'+w+'px">'+(b.k==='cur'?'<span class="pf" id="pf"></span><span class="pl" id="pl"></span>':'')+'<div class="art">'+artT(b.i)+'</div><div class="t"><div class="n">'+esc(x.t)+'</div><div class="a">'+(x.off?'Unavailable, will be skipped':sub)+'</div></div></div>';});
  var end=seq.length?seq[seq.length-1].s+T[seq[seq.length-1].i].d:0;
  if(LIVE&&seq.length&&!nUpCount())h+='<div class="qempty" style="left:'+(end*PPS+16)+'px">Queue is empty</div>';
  h+='<div class="ruler">';
  var first=Math.ceil(clock0/30000)*30000;
  for(var ms=first;ms<clock0+end*1000;ms+=30000){var x=(ms-clock0)/1000*PPS,maj=(Math.round(ms/30000)%4===0);h+='<span class="tick'+(maj?' maj':'')+'" style="left:'+x+'px"></span>'+(maj?'<span class="tlab" style="left:'+x+'px">'+clk(ms)+'</span>':'');}
  h+='</div>';
  $('strip').innerHTML=h;
  var nUp=seq.filter(function(b){return b.k!=='past'&&b.k!=='cur';}).length;
  $('upn').innerHTML=nUp?nUp+' up next · queue runs to '+clk(clock0+end*1000):'Queue is empty';
  posStrip();
}
function posStrip(){
  var c=curS(),x=(c+st.t)*PPS;$('strip').style.transform='translateX('+(CX-x)+'px)';
  var pf=$('pf');if(pf){pf.style.width=(st.t*PPS)+'px';$('pl').style.width=(st.t*PPS)+'px';}
  $('nowl').textContent='Now · '+clk(nowMs());
}
function renderNow(){
  var x=T[st.cur],p=x.pal||PAL[st.cur%PAL.length];
  $('cover').innerHTML=artT(st.cur);
  $('amb').style.background='radial-gradient(1100px 600px at 14% 0%,'+hexA(p[1],.40)+',transparent 70%),radial-gradient(800px 500px at 90% 10%,'+hexA(p[2],.14)+',transparent 70%)';
  $('ttl').textContent=x.t;
  $('who').innerHTML='<a>'+esc(x.a)+'</a><div class="alb">'+esc(x.al)+(x.y?' · '+x.y:'')+'</div>';
  $('chips').innerHTML=(x.bpm!=null?'<span class="chip"><b>'+x.bpm+'</b>BPM</span>':'')+(x.key?'<span class="chip"><b>'+esc(x.key)+'</b></span>':'')+(x.en!=null?'<span class="chip">Energy <b>'+x.en+'%</b></span>':'')+(x.pc!=null?'<span class="chip"><b>'+x.pc+'</b>plays</span>':'');
  renderLike();renderStrip();renderPane();renderTime();
}
function renderLike(){var on=!!st.liked[st.cur];$('like').innerHTML=on?I.heartF:I.heart;$('like').classList.toggle('on',on);}
function renderTime(){var x=T[st.cur];$('el').textContent=fmt(st.t);$('ends').textContent='of '+fmt(x.d)+' · ends '+clk(nowMs()+(x.d-st.t)*1000);if(st.tab==='lyrics')markLyric();}
function renderTrans(){
  $('pp').innerHTML=st.playing?I.pause:I.play;
  $('shuf').classList.toggle('on',st.shuffle);
  $('rep').classList.toggle('on',st.repeat>0);$('repb').textContent=st.repeat===2?'1':'';
  $('np').innerHTML=(st.playing?eqg():'')+(st.playing?'Playing':'Paused')+(st.ctx?' from <b>'+esc(st.ctx)+'</b>':'');
  document.querySelectorAll('.eqg').forEach(function(e){e.classList.toggle('paused',!st.playing);});
}
function renderVol(){var v=st.muted?0:st.vol;$('vol').querySelector('.fl').style.width=(v*100)+'%';$('vol').querySelector('.th').style.left=(v*100)+'%';$('mute').innerHTML=v===0?I.mute:I.vol;}
function renderPane(){
  $('tabs').querySelectorAll('button').forEach(function(b){b.classList.toggle('on',b.dataset.t===st.tab);});
  var x=T[st.cur],h='',pane=$('pane');pane.classList.toggle('plain',st.tab!=='lyrics'||!x.ly);
  if(st.tab==='lyrics'){
    if(x.ly)h='<div class="lyr" id="lyr">'+x.ly.map(function(l){return '<p data-s="'+l[0]+'">'+l[1]+'</p>';}).join('')+'<div class="src-l">Synced lyrics from LRCLIB</div></div>';
    else h='<div class="empty"><div class="ic">'+I.lyrics+'</div><h4>No synced lyrics for this one</h4><p>LRCLIB doesn’t have this track yet. Try Credits or About.</p></div>';
  }else if(st.tab==='credits'){
    h='<div class="cred">'+(x.cr?x.cr.map(function(c){return '<div class="grp"><div class="k">'+c[0]+'</div>'+c.slice(1).map(function(p){return '<div class="p">'+p[0]+(p[1]?'<span>'+p[1]+'</span>':'')+'</div>';}).join('')+'</div>';}).join('')+'<div class="src-l">Credits from MusicBrainz</div>':'<div class="empty"><div class="ic">'+I.more+'</div><h4>No credits found</h4><p>MusicBrainz has no recording credits for this track.</p></div>')+'</div>';
  }else{
    var F=[];
    function fact(k,v,src){F.push('<div class="fact"><div class="k">'+k+'</div><div class="v m">'+esc(v)+'</div><div class="s">'+esc(src)+'</div></div>');}
    if(x.pc!=null){fact('Your plays',x.pc,'Last.fm');fact('Listeners',(x.pc*4127+18233).toLocaleString('en-US'),'Last.fm');}
    if(x.bpm!=null)fact('Tempo',x.bpm+' BPM','ReccoBeats');
    if(x.key)fact('Key',x.key,'ReccoBeats');
    var tn=LIVE?(x.tn||null):(st.cur%9+2)+' of 11';
    if(tn)fact('Track',tn,x.al);
    if(x.y)fact('Released',x.y,'Spotify');
    h=F.length?'<div class="facts">'+F.join('')+'</div>':'<div class="empty"><div class="ic">'+I.more+'</div><h4>Nothing to show yet</h4><p>Spotify did not return details for this track.</p></div>';
  }
  pane.innerHTML=h;pane.scrollTop=0;
  if(st.tab==='lyrics')markLyric(true);
}
function markLyric(jump){
  var ps=document.querySelectorAll('#lyr p');if(!ps.length)return;var k=-1;
  ps.forEach(function(p,i){if(+p.dataset.s<=st.t)k=i;});
  ps.forEach(function(p,i){p.classList.toggle('now',i===k);});
  var key=String(k);if($('lyr').dataset.k===key)return;$('lyr').dataset.k=key;
  var pane=$('pane'),tgt=k>=0?ps[k]:ps[0];pane.scrollTo({top:Math.max(0,tgt.offsetTop-pane.clientHeight/2+20),behavior:jump?'auto':'smooth'});
}
function renderDev(){var d=DEV[st.dev];$('devb').innerHTML=d?I[d[0]]+esc(d[1]):I.devices+'No device';}
function renderLib(){
  if(LIVE){$('library').innerHTML='<div class="lh"><h2>Library</h2></div><div class="empty"><div class="ic">'+I.search+'</div><h4>Your library arrives in the next step</h4><p>Playlists and saved albums will load from Spotify here.</p></div>';return;}
  $('library').innerHTML='<div class="lh"><h2>Library</h2><div class="flt" id="flt"><button class="chip sel">All</button><button class="chip">Playlists</button><button class="chip">Albums</button><button class="chip">Artists</button></div></div><div class="grid">'+
    PLS.concat([["Concrete Orchard","Album · Ines Varga",1],["Two Rooms","Album · Okoro & Wren",3],["Rest Stops","Album · Dalton Reyes",5]]).map(function(p,i){return '<div class="card'+(p[0]===st.ctx?' on':'')+'" data-c="'+p[0]+'"><div class="art">'+art(p[2]+i)+'</div><div class="n">'+p[0]+'</div><div class="m">'+p[1]+'</div></div>';}).join('')+'</div>';
}
function setView(v){st.view=v;$('views').querySelectorAll('button').forEach(function(b){b.classList.toggle('on',b.dataset.v===v);});$('listen').hidden=v!=='listen';$('library').hidden=v!=='library';if(v==='library')renderLib();}
function play(i){if(T[i].off)return;st.cur=i;st.t=0;renderNow();}
function advance(){if(st.repeat===2){st.t=0;renderTime();posStrip();return;}hist.push(st.cur);if(hist.length>3)ctxQ.push(hist.shift());var i=userQ.length?userQ.shift():ctxQ.shift();while(T[i].off){ctxQ.push(i);i=ctxQ.shift();}play(i);}
function back(){if(st.t>3||!hist.length){st.t=0;renderTime();posStrip();return;}ctxQ.unshift(st.cur);play(hist.pop());}
function jumpTo(k){var b=seq[k];if(!b||b.k==='cur'||T[b.i].off)return;
  if(LIVE){var ci=seq.findIndex(function(x){return x.k==='cur';});if(b.k==='past')call('play_track',T[b.i].uri);else call('jump_ahead',k-ci,T[b.i].uri);return;}
  if(b.k==='past'){var j=hist.indexOf(b.i);var after=hist.splice(j);after.shift();ctxQ=after.concat([st.cur]).concat(ctxQ);play(b.i);return;}
  hist.push(st.cur);if(hist.length>3)ctxQ.push(hist.shift());
  var ups=seq.filter(function(x){return x.k==='mine'||x.k==='next';}),pos=ups.indexOf(b);
  ups.slice(0,pos).forEach(function(x){if(!T[x.i].off){hist.push(x.i);if(hist.length>3)ctxQ.push(hist.shift());}});
  userQ=ups.slice(pos+1).filter(function(x){return x.k==='mine';}).map(function(x){return x.i;});
  ctxQ=ups.slice(pos+1).filter(function(x){return x.k==='next';}).map(function(x){return x.i;});
  play(b.i);}

/* palette */
var pi=0,pres=[];
function openPal(){$('pal').classList.add('open');$('q').value='';filt();setTimeout(function(){$('q').focus();},0);}
function closePal(){$('pal').classList.remove('open');}
function filt(){var q=$('q').value.toLowerCase().trim();pres=[];
  T.forEach(function(x,i){if(x.off)return;var hit=!q||x.t.toLowerCase().indexOf(q)>-1||x.a.toLowerCase().indexOf(q)>-1;var ly=null;if(!hit&&q.length>2&&x.ly)x.ly.forEach(function(l){if(!ly&&l[1].toLowerCase().indexOf(q)>-1)ly=l;});if(hit||ly)pres.push({type:'song',i:i,ly:ly});});
  PLS.forEach(function(p,i){if(!q||p[0].toLowerCase().indexOf(q)>-1)pres.push({type:'pl',p:p,i:i});});
  pres=pres.slice(0,8);pi=0;drawPal();}
function drawPal(){var h='',lastT='';pres.forEach(function(r,k){var g=r.type==='song'?'Songs':'Playlists and albums';if(g!==lastT){h+='<div class="gh">'+g+'</div>';lastT=g;}
  if(r.type==='song'){var x=T[r.i];h+='<div class="r'+(k===pi?' sel':'')+'" data-k="'+k+'"><div class="art">'+artT(r.i)+'</div><div><div class="n">'+esc(x.t)+'</div><div class="m">'+(r.ly?'“'+esc(r.ly[1])+'” at '+fmt(r.ly[0]):esc(x.a)+' · '+fmt(x.d))+'</div></div><kbd>↵</kbd></div>';}
  else h+='<div class="r'+(k===pi?' sel':'')+'" data-k="'+k+'"><div class="art">'+art(r.p[2]+r.i)+'</div><div><div class="n">'+r.p[0]+'</div><div class="m">'+r.p[1]+'</div></div><kbd>↵</kbd></div>';});
  $('res').innerHTML=h||'<div class="empty" style="padding:24px 10px"><h4>Nothing matches</h4><p>Try an artist, a song or a line from the lyrics.</p></div>';}
function pick(k,queue){var r=pres[k];if(!r)return;closePal();
  if(r.type==='pl'){st.ctx=r.p[0];renderTrans();setView('listen');return;}
  if(queue){userQ.push(r.i);var j=ctxQ.indexOf(r.i);if(j>-1)ctxQ.splice(j,1);renderStrip();return;}
  setView('listen');var j2=ctxQ.indexOf(r.i);if(j2>-1)ctxQ.splice(j2,1);j2=userQ.indexOf(r.i);if(j2>-1)userQ.splice(j2,1);hist.push(st.cur);if(hist.length>3)ctxQ.push(hist.shift());play(r.i);if(r.ly){st.t=r.ly[0];renderTime();posStrip();}}


/* ---------- Live mode: state pushed from Python (window.meridian.update) ---------- */
var liveSeq=[],ENR={},REP=['off','context','track'],lastSeek=0,lastVol=0,lastEnd=0,seekT=0,volT=0,curId=null,toastT=0;
app.insertAdjacentHTML('beforeend','<div class="gate" id="gate" hidden></div><div class="toast" id="toast"></div>');
function toast(msg){var t=$('toast');t.textContent=msg;t.classList.add('show');clearTimeout(toastT);toastT=setTimeout(function(){t.classList.remove('show');},4000);}
function apiObj(){return window.pywebview&&window.pywebview.api&&window.pywebview.api.boot?window.pywebview.api:null;}
function call(name){var a=apiObj();if(!a)return;var args=[].slice.call(arguments,1);
  return a[name].apply(a,args).then(function(r){if(r&&r.ok===false){toast(r.error);a.refresh();}return r;}).catch(function(){toast('Lost contact with Meridian.');});}
function seekLive(){lastSeek=Date.now();clearTimeout(seekT);seekT=setTimeout(function(){call('seek',Math.round(st.t*1000));},250);}
function volLive(ms){lastVol=Date.now();clearTimeout(volT);volT=setTimeout(function(){call('set_volume',Math.round((st.muted?0:st.vol)*100));},ms==null?250:ms);}
var GATES={
  connecting:['radio','Connecting to Spotify','Looking for what is playing.'],
  waiting:['radio','Finish in your browser','Approve Meridian in the Spotify window that just opened.'],
  logged_out:['radio','Connect Spotify','Meridian shows and controls what is playing on your Spotify devices. Playback control needs Spotify Premium.','Connect Spotify','login'],
  setup_required:['sliders','Add your Spotify client ID','','',''],
  no_device:['devices','No active device','Open Spotify on this computer, a phone or a speaker and press play, or pick a device below.','Check again','refresh']
};
function showGate(kind,s){
  var g=$('gate');if(!kind){g.hidden=true;app.classList.remove('gated');return;}
  var d=GATES[kind],msg=(kind==='setup_required'&&s&&s.message)||d[2];
  var devs=kind==='no_device'&&s&&s.devices?s.devices.filter(function(x){return !x.is_restricted;}).map(function(x){return '<button class="btn" data-dev="'+esc(x.id)+'">'+I[devIcon(x.type)]+esc(x.name)+'</button>';}).join(''):'';
  g.innerHTML='<div class="gate-in"><div class="empty"><div class="ic">'+I[d[0]]+'</div><h4>'+d[1]+'</h4><p>'+esc(msg)+'</p></div>'+(devs?'<div class="gate-devs">'+devs+'</div>':'')+(d[3]?'<div class="gate-acts"><button class="btn primary" data-act="'+d[4]+'">'+d[3]+'</button></div>':'')+'</div>';
  g.hidden=false;app.classList.add('gated');
}
$('gate').onclick=function(e){
  var dv=e.target.closest('[data-dev]');if(dv){call('transfer',dv.dataset.dev);return;}
  var b=e.target.closest('[data-act]');if(!b)return;
  if(b.dataset.act==='refresh'){call('refresh');return;}
  showGate('waiting');
  var a=apiObj();a.login().then(function(r){if(r&&r.ok===false){toast(r.error);showGate('logged_out');}}).catch(function(){showGate('logged_out');});
};
document.querySelector('.av').title='Disconnect Spotify';
document.querySelector('.av').style.cursor='pointer';
document.querySelector('.av').onclick=function(){if(LIVE&&window.confirm('Disconnect Spotify?'))call('logout');};
function devIcon(t){t=(t||'').toLowerCase();return t==='computer'?'laptop':t==='smartphone'||t==='tablet'?'phone':'speaker';}
function hashPal(id){var h=0;for(var i=0;i<id.length;i++)h=(h*31+id.charCodeAt(i))|0;return PAL[Math.abs(h)%PAL.length];}
function bootLive(){
  PLS.length=0;T.length=0;hist.length=0;userQ.length=0;ctxQ.length=0;DEV.length=0;
  T.push({t:'',a:'',al:'',y:null,d:1});st.cur=0;st.t=0;st.playing=false;st.liked={};st.ctx=null;st.dev=0;
  renderTrans();renderVol();renderDev();showGate('connecting');
  function run(){window.pywebview.api.boot().then(window.meridian.update);}
  if(apiObj())run();else window.addEventListener('pywebviewready',run);
}
function mapTrack(tr){
  var x={id:tr.id,uri:tr.uri,t:tr.title,a:tr.artist,al:tr.album,y:tr.year,d:Math.max(1,tr.duration_ms/1000),img:tr.art_url,tn:tr.track_number&&tr.album_tracks?tr.track_number+' of '+tr.album_tracks:null,pal:hashPal(tr.id)};
  var e=ENR[tr.id];if(e)for(var k in e)x[k]=e[k];return x;
}
window.meridian={update:function(s){
  if(s.status!=='ready'){
    if(s.status==='no_device'){DEV.length=0;fillDev(s.devices);renderDev();}
    showGate(s.status,s);curId=null;st.playing=false;return;
  }
  showGate(null);
  var tr=s.track,changed=tr.id!==curId;
  st.playing=s.is_playing;st.shuffle=s.shuffle;st.repeat=Math.max(0,REP.indexOf(s.repeat));st.ctx=s.context_name;
  if(s.volume!=null&&Date.now()-lastVol>1500){if(s.volume>0){st.vol=s.volume;st.muted=false;}else if(!st.muted)st.vol=0;}
  DEV.length=0;fillDev(s.devices);st.dev=Math.max(0,s.devices.findIndex(function(d){return d.is_active;}));
  renderTrans();renderVol();renderDev();
  if(dragX!==null)return; /* never rebuild the strip under the user's finger */
  /* Timeline: Python decides order, kinds and offsets; offsets are shifted so the first block starts at 0 */
  var blocks=(s.timeline&&s.timeline.blocks)||[{kind:'cur',track:tr,start_ms:0}];
  var first=blocks[0].start_ms;T.length=0;liveSeq=[];
  blocks.forEach(function(b,k){T.push(mapTrack(b.track));liveSeq.push({i:k,s:(b.start_ms-first)/1000,k:b.kind});if(b.kind==='cur')st.cur=k;});
  st.liked={};st.liked[st.cur]=s.liked;
  if(Date.now()-lastSeek>1500){var lag=s.is_playing?Math.min(5000,Math.max(0,Date.now()-s.fetched_at_ms)):0;st.t=Math.min(T[st.cur].d,(s.progress_ms+lag)/1000);}
  if(changed){curId=tr.id;renderNow();}else{renderLike();renderStrip();renderTime();}
}};
function fillDev(ds){(ds||[]).forEach(function(d){DEV.push([devIcon(d.type),d.name,d.is_restricted?'Not controllable':d.is_active?'Spotify Connect · Active':'Spotify Connect',d.is_restricted?1:0,d.id]);});}

/* events */
$('pp').onclick=function(){st.playing=!st.playing;renderTrans();if(LIVE)call('set_playing',st.playing);};
$('next').onclick=function(){if(LIVE)call('next');else advance();};$('prev').onclick=function(){if(LIVE)call('previous');else back();};
$('shuf').onclick=function(){st.shuffle=!st.shuffle;renderTrans();if(LIVE)call('set_shuffle',st.shuffle);};
$('rep').onclick=function(){st.repeat=(st.repeat+1)%3;renderTrans();if(LIVE)call('set_repeat',REP[st.repeat]);};
$('like').onclick=function(){st.liked[st.cur]=!st.liked[st.cur];renderLike();if(LIVE)call('set_saved',T[st.cur].id,!!st.liked[st.cur]);};
$('mute').onclick=function(){st.muted=!st.muted;renderVol();if(LIVE)volLive();};
$('tabs').onclick=function(e){var b=e.target.closest('button');if(b){st.tab=b.dataset.t;renderPane();}};
$('views').onclick=function(e){var b=e.target.closest('button');if(b)setView(b.dataset.v);};
$('library').onclick=function(e){var f=e.target.closest('.chip');if(f){$('flt').querySelectorAll('.chip').forEach(function(c){c.classList.toggle('sel',c===f);});return;}var c=e.target.closest('.card');if(c){st.ctx=c.dataset.c;renderTrans();setView('listen');}};
$('pane').onclick=function(e){var p=e.target.closest('#lyr p');if(p){st.t=+p.dataset.s;renderTime();posStrip();if(LIVE)seekLive();}};
$('cmdb').onclick=function(){if(LIVE){toast('Search arrives with the Library step.');return;}openPal();};
$('pal').onmousedown=function(e){if(e.target.id==='pal')closePal();};
$('q').oninput=filt;
$('res').onclick=function(e){var r=e.target.closest('.r');if(r)pick(+r.dataset.k,e.shiftKey);};
$('q').onkeydown=function(e){if(e.key==='ArrowDown'){e.preventDefault();pi=Math.min(pres.length-1,pi+1);drawPal();}if(e.key==='ArrowUp'){e.preventDefault();pi=Math.max(0,pi-1);drawPal();}if(e.key==='Enter')pick(pi,e.shiftKey);if(e.key==='Escape')closePal();};
var tl=$('tl'),dragX=null,dragT=0,moved=false;
tl.addEventListener('mousedown',function(e){dragX=e.clientX;dragT=st.t;moved=false;});
window.addEventListener('mousemove',function(e){if(dragX===null)return;var sc=app.getBoundingClientRect().width/1440,dx=(e.clientX-dragX)/sc;if(Math.abs(dx)>3){moved=true;tl.classList.add('drag');}if(moved){st.t=Math.max(0,Math.min(T[st.cur].d-1,dragT-dx/PPS));renderTime();posStrip();}});
window.addEventListener('mouseup',function(e){if(dragX===null)return;var wasMoved=moved;dragX=null;tl.classList.remove('drag');if(wasMoved){renderStrip();if(LIVE){lastSeek=Date.now();call('seek',Math.round(st.t*1000));}return;}var b=e.target.closest&&e.target.closest('.blk');if(b)jumpTo(+b.dataset.k);});
var vol=$('vol');vol.addEventListener('mousedown',function(e){function set(ev){var r=vol.getBoundingClientRect();st.vol=Math.max(0,Math.min(1,(ev.clientX-r.left)/r.width));st.muted=false;renderVol();}set(e);function up(){window.removeEventListener('mousemove',set);window.removeEventListener('mouseup',up);if(LIVE)volLive(0);}window.addEventListener('mousemove',set);window.addEventListener('mouseup',up);});
function openDev(){var pop=$('pop');if(pop.classList.contains('open')){pop.classList.remove('open');return;}
  pop.innerHTML='<div class="ph"><span class="hd">Play on</span></div>'+DEV.map(function(d,i){return '<div class="it'+(i===st.dev?' on':'')+(d[3]?' off':'')+'" data-d="'+i+'"><div class="ic">'+I[d[0]]+'</div><div><div class="n">'+esc(d[1])+'</div><div class="m">'+esc(d[2])+'</div></div>'+(i===st.dev?eqg():'')+'</div>';}).join('');
  var a=app.getBoundingClientRect(),r=$('devb').getBoundingClientRect(),sc=a.width/1440;pop.classList.add('open');pop.style.left=((r.right-a.left)/sc-300)+'px';pop.style.top=((r.bottom-a.top)/sc+8)+'px';}
$('devb').onclick=openDev;
$('pop').onclick=function(e){var it=e.target.closest('.it');if(!it||it.classList.contains('off'))return;st.dev=+it.dataset.d;renderDev();if(LIVE)call('transfer',DEV[st.dev][4]);$('pop').classList.remove('open');};
document.addEventListener('mousedown',function(e){if(!e.target.closest('#pop')&&!e.target.closest('#devb'))$('pop').classList.remove('open');});
document.addEventListener('keydown',function(e){
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('cmdb').onclick();return;}
  if(e.target.tagName==='INPUT')return;
  if(e.key==='/'){e.preventDefault();$('cmdb').onclick();return;}
  if(e.code==='Space'){e.preventDefault();$('pp').onclick();}
  if(e.key==='ArrowRight'){st.t=Math.min(T[st.cur].d-1,st.t+5);renderTime();posStrip();if(LIVE)seekLive();}
  if(e.key==='ArrowLeft'){st.t=Math.max(0,st.t-5);renderTime();posStrip();if(LIVE)seekLive();}
  if(e.key==='ArrowUp'){e.preventDefault();st.vol=Math.min(1,st.vol+.05);renderVol();if(LIVE)volLive();}
  if(e.key==='ArrowDown'){e.preventDefault();st.vol=Math.max(0,st.vol-.05);renderVol();if(LIVE)volLive();}
  if(e.key==='s')$('shuf').click();if(e.key==='r')$('rep').click();if(e.key==='l')setView(st.view==='listen'?'library':'listen');
  if(e.key==='Escape'){$('pop').classList.remove('open');closePal();}});
setView('listen');if(LIVE)bootLive();else{renderNow();renderTrans();renderVol();renderDev();}
setInterval(function(){if(!st.playing||dragX!==null)return;st.t+=.25;if(st.t>=T[st.cur].d){if(LIVE){st.t=T[st.cur].d;if(Date.now()-lastEnd>2000){lastEnd=Date.now();call('refresh');}return;}advance();return;}renderTime();posStrip();},250);
})();

/* Fit the 1440x900 canvas to the window. */
(function(){var a=document.getElementById('app');if(!a)return;a.style.transformOrigin='top left';function f(){var s=Math.min(1,innerWidth/1440,innerHeight/900);a.style.transform='scale('+s+')';document.body.style.height=(900*s)+'px';document.body.style.width=(1440*s)+'px';}addEventListener('resize',f);f();})();
