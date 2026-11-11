import {paintEffect,paintOverlay,decodeGif,encodeEffectGif} from './effects.js';
const $=id=>document.getElementById(id), canvas=$('canvas'),ctx=canvas.getContext('2d');
let worker,context,recorder,source,raf,abort=false,urls=[],recognitionReject;
const colors={violet:'#b99aff',ember:'#ff875d',ocean:'#43d9dc'};
const fields=['title','aspect','resolution','theme','mode','timings','effect','intensity','fxspeed','blend','position','opacity','scale'];
let overlayAsset=null,previewRaf=null,previewStart=0;
const controls=[...fields,'audio','demo','overlay','previewfx','clearoverlay','exportgif'];
const fxConfig=()=>({preset:$('effect').value,intensity:+$('intensity').value,speed:+$('fxspeed').value,color:colors[$('theme').value]});
const overlayConfig=()=>({opacity:+$('opacity').value,scale:+$('scale').value,blend:$('blend').value,position:$('position').value,speed:+$('fxspeed').value});
function stopPreview(){cancelAnimationFrame(previewRaf);previewRaf=null;$('previewfx').textContent='Preview effects'}
try{const saved=JSON.parse(localStorage.getItem('zerox-project')||'{}');for(const id of fields)if(saved[id]!=null)$(id).value=saved[id]}catch{}
for(const id of fields)$(id).addEventListener('change',()=>{try{localStorage.setItem('zerox-project',JSON.stringify(Object.fromEntries(fields.map(k=>[k,$(k).value]))))}catch{};draw(0,0,[])});
function status(s,error=false){$('status').textContent=s;$('status').classList.toggle('error',error)}
function layout(){const s=+$('resolution').value;const a=$('aspect').value;canvas.width=a==='landscape'?Math.round(s*16/9):s;canvas.height=a==='portrait'?Math.round(s*16/9):s}
function draw(t,energy,words){const w=canvas.width,h=canvas.height,accent=colors[$('theme').value];ctx.fillStyle='#0b0a16';ctx.fillRect(0,0,w,h);const x=w*(.5+.08*Math.sin(t*.3)),y=h*.41;
 const grad=ctx.createRadialGradient(x,y,1,x,y,w*.6);grad.addColorStop(0,accent+'45');grad.addColorStop(1,'#0b0a1600');ctx.fillStyle=grad;ctx.fillRect(0,0,w,h);
 for(let i=0;i<6;i++){ctx.beginPath();ctx.arc(x,y,w*(.09+i*.03+energy*.025),0,Math.PI*2);ctx.strokeStyle=accent+(30+i*5).toString(16);ctx.lineWidth=w/400;ctx.stroke()}
 paintEffect(ctx,w,h,t,energy,fxConfig());paintOverlay(ctx,w,h,t,overlayAsset,overlayConfig());
 ctx.textAlign='left';ctx.fillStyle=accent;ctx.font=`600 ${w/65}px system-ui`;ctx.fillText('ZEROX / LYRIC MOTION',w*.06,h*.09);ctx.fillStyle='#faf7ff';ctx.font=`700 ${w/35}px system-ui`;ctx.fillText($('title').value,w*.06,h*.16,w*.87);
 const idx=words.findIndex(z=>t>=z.start&&t<=z.end);if(idx>=0){let start=Math.floor(idx/6)*6;let group=words.slice(start,start+6);ctx.font=`750 ${w/23}px system-ui`;const lines=[];let line=[];for(const z of group){if(line.length&&ctx.measureText([...line,z].map(x=>x.text).join(' ')).width>w*.86){lines.push(line);line=[]}line.push(z)}if(line.length)lines.push(line);lines.forEach((line,j)=>{let x=(w-ctx.measureText(line.map(z=>z.text).join(' ')).width)/2;for(const z of line){ctx.fillStyle=t>=z.start&&t<=z.end?accent:'#f6f3ff';ctx.fillText(z.text,x,h*.53+j*w*.065);x+=ctx.measureText(z.text+' ').width}})}
 for(let b=0;b<56;b++){ctx.fillStyle=accent;let bh=h*(.008+energy*.16*Math.abs(Math.sin(b*.63+t*2)));ctx.fillRect(w*(.07+.86*b/56),h*.85-bh,w/100,bh)}ctx.fillStyle='#2d293c';ctx.fillRect(w*.06,h*.93,w*.88,h*.004);if(window.songDuration){ctx.fillStyle=accent;ctx.fillRect(w*.06,h*.93,w*.88*Math.min(1,t/window.songDuration),h*.004)}}
layout();draw(0,.2,[]);
function recognize(audio){return new Promise((resolve,reject)=>{recognitionReject=reject;worker??=new Worker('./worker.js',{type:'module'});worker.onerror=e=>reject(Error(e.message||'Speech worker could not load. Check your connection.'));worker.onmessage=({data})=>{if(data.type==='loading')status(`Loading recognition model${data.progress?' · '+Math.round(data.progress)+'%':''}. First use can take a few minutes.`);if(data.type==='done')resolve(data.words);if(data.type==='error')reject(Error(data.message))};worker.postMessage({audio},[audio.buffer])})}
function download(blob,name,label){const a=document.createElement('a'),url=URL.createObjectURL(blob);urls.push(url);a.href=url;a.download=name;a.className='download';a.textContent=label;$('downloads').append(a)}
function srt(words){const ts=t=>{const n=Math.round(t*1000);return `${String(Math.floor(n/3600000)).padStart(2,'0')}:${String(Math.floor(n/60000)%60).padStart(2,'0')}:${String(Math.floor(n/1000)%60).padStart(2,'0')},${String(n%1000).padStart(3,'0')}`};let text='';for(let i=0;i<words.length;i+=6){const g=words.slice(i,i+6);text+=`${i/6+1}\n${ts(g[0].start)} --> ${ts(g.at(-1).end)}\n${g.map(x=>x.text).join(' ')}\n\n`}return text}
$('demo').onclick=async()=>{try{const data=await fetch('./demo.mp3').then(r=>{if(!r.ok)throw Error('Demo could not load');return r.blob()});const transfer=new DataTransfer();transfer.items.add(new File([data],'ZeroX-demo.mp3',{type:'audio/mpeg'}));$('audio').files=transfer.files;status('Demo loaded. Press Create my video to test automatic lyrics and export.')}catch(e){status(e.message,true)}};
$('cancel').onclick=()=>{abort=true;recognitionReject?.(Error('Cancelled'));recognitionReject=null;try{source?.stop()}catch{};if(recorder?.state==='recording')recorder.stop();worker?.terminate();worker=null;status('Export cancelled.');};
$('create').onclick=async()=>{
 abort=false;stopPreview();for(const id of controls)$(id).disabled=true;$('create').disabled=true;$('cancel').hidden=false;$('progress').value=0;let stream;
 try{
  const file=$('audio').files[0];if(!file)throw Error('Choose an audio file first.');if(file.size>150*1024*1024)throw Error('Maximum audio size is 150 MB.');if(!window.MediaRecorder||!canvas.captureStream)throw Error('Video export needs a browser with MediaRecorder and canvas capture. Try current Chrome or Edge.');
  status('Reading your song…');context=new AudioContext();await context.resume();const buffer=await context.decodeAudioData(await file.arrayBuffer());if(buffer.duration>600)throw Error('Maximum song length is 10 minutes.');window.songDuration=buffer.duration;
  let words=[];
  if($('mode').value==='timed'){words=JSON.parse($('timings').value);if(!Array.isArray(words)||words.some(z=>typeof z.text!=='string'||!Number.isFinite(z.start)||!Number.isFinite(z.end)||z.start<0||z.end<=z.start))throw Error('Timings must contain text, nonnegative start, and an end after start.');words.sort((a,b)=>a.start-b.start)}
  if($('mode').value==='auto'){
   status('Preparing audio for lyric recognition…');const offline=new OfflineAudioContext(1,Math.ceil(buffer.duration*16000),16000);const input=offline.createBufferSource();input.buffer=buffer;input.connect(offline.destination);input.start();const mono=await offline.startRendering();words=await recognize(mono.getChannelData(0).slice());$('timings').value=JSON.stringify(words,null,2);
  }
  if(abort)return;layout();draw(0,0,words);$('canvas').hidden=false;$('result').hidden=true;$('result').pause();$('downloads').replaceChildren();urls.forEach(URL.revokeObjectURL);urls=[];
  download(new Blob([JSON.stringify(words,null,2)],{type:'application/json'}),'lyrics.json','Lyric timings');download(new Blob([srt(words)],{type:'text/plain'}),'lyrics.srt','Subtitles');$('downloads').hidden=false;
  const analyser=context.createAnalyser();analyser.fftSize=256;const bins=new Uint8Array(analyser.frequencyBinCount);const dest=context.createMediaStreamDestination();source=context.createBufferSource();source.buffer=buffer;source.connect(analyser);analyser.connect(dest);analyser.connect(context.destination);stream=canvas.captureStream(30);dest.stream.getAudioTracks().forEach(track=>stream.addTrack(track));
  const mime=['video/mp4;codecs=avc1.42E01E,mp4a.40.2','video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'].find(s=>MediaRecorder.isTypeSupported(s));if(!mime)throw Error('This browser has no supported video encoder. Try Chrome.');const chunks=[];recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:6000000,audioBitsPerSecond:192000});
  const stopped=new Promise((resolve,reject)=>{recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};recorder.onerror=e=>reject(Error(e.error?.message||'Video encoder failed'));recorder.onstop=resolve});recorder.start(1000);const start=context.currentTime;
  function frame(){const t=context.currentTime-start;analyser.getByteFrequencyData(bins);const energy=bins.reduce((a,b)=>a+b,0)/bins.length/180;draw(t,energy,words);$('progress').value=Math.min(1,t/buffer.duration);if(t<buffer.duration&&!abort){status(`Rendering ${Math.floor(t)}s / ${Math.ceil(buffer.duration)}s · keep this tab visible`);raf=requestAnimationFrame(frame)}}
  source.onended=()=>{if(recorder.state==='recording')recorder.stop()};source.start();frame();await stopped;if(abort)return;
  const blob=new Blob(chunks,{type:mime});if(!blob.size)throw Error('The browser returned an empty video.');const url=URL.createObjectURL(blob);urls.push(url);$('result').src=url;$('result').hidden=false;$('canvas').hidden=true;download(blob,'ZeroX-music-video.'+(mime.startsWith('video/mp4')?'mp4':'webm'),'Download video');$('progress').value=1;status(words.length?'Your video is ready. Preview it and review the recognized lyrics before publishing.':'Your visualizer is ready. No lyric words were detected or lyrics were disabled.');
 }catch(e){if(!abort)status(e.message,true)}finally{cancelAnimationFrame(raf);if(source){try{source.stop()}catch{}}stream?.getTracks().forEach(t=>t.stop());if(context&&context.state!=='closed')await context.close();for(const id of controls)$(id).disabled=false;$('create').disabled=false;$('cancel').hidden=true}
};

$('previewfx').onclick=()=>{
 if(previewRaf!==null){stopPreview();return}layout();$('canvas').hidden=false;$('result').hidden=true;previewStart=performance.now();$('previewfx').textContent='Stop preview';
 const step=now=>{draw((now-previewStart)/1000,.35,[]);previewRaf=requestAnimationFrame(step)};previewRaf=requestAnimationFrame(step);
};
$('overlay').onchange=async()=>{const f=$('overlay').files[0];if(!f)return;try{
 if(f.size>8*1024*1024)throw Error('Overlay limit is 8 MB.');
 if(!['image/gif','image/png','image/jpeg','image/webp'].includes(f.type))throw Error('Choose a GIF, PNG, JPEG or WebP image.');
 let asset;if(f.type==='image/gif')asset=decodeGif(await f.arrayBuffer());else{const image=await createImageBitmap(f);if(image.width>4096||image.height>4096){image.close();throw Error('Image dimensions must be 4096px or smaller.')}asset={image,width:image.width,height:image.height}}
 overlayAsset?.image?.close?.();overlayAsset=asset;$('overlayinfo').textContent=`${f.name} · ${asset.width} × ${asset.height}${asset.frames?' · '+asset.frames.length+' animated frames':''} · ready`;draw(0,.35,[]);status('Overlay loaded. Preview it or create your video.');
 }catch(e){$('overlay').value='';status(e.message,true)}
};
$('clearoverlay').onclick=()=>{overlayAsset?.image?.close?.();overlayAsset=null;$('overlay').value='';$('overlayinfo').textContent='Overlay cleared.';draw(0,.2,[])};
$('exportgif').onclick=async()=>{stopPreview();for(const id of controls)$(id).disabled=true;$('create').disabled=true;try{
 if($('effect').value==='none')throw Error('Choose an effect to generate a GIF.');const c=document.createElement('canvas');c.width=480;c.height=270;
 const data=await encodeEffectGif(c,fxConfig(),{onProgress:p=>{status(`Generating your effect GIF · ${Math.round(p*100)}%`)},color:colors[$('theme').value]});
 download(new Blob([data],{type:'image/gif'}),'ZeroX-'+$('effect').value+'.gif','Download effect GIF');$('downloads').hidden=false;status('Effect GIF ready. Download it, then add it as an overlay wherever you want.');
 }catch(e){status(e.message,true)}finally{for(const id of controls)$(id).disabled=false;$('create').disabled=false}
};
