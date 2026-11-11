import {parseGIF,decompressFrames} from './vendor/gifuct.js';
export const PRESETS=['none','stars','rain','embers','glitch','grain'];
const unit=n=>{const v=Math.sin(n*127.1+311.7)*43758.5453;return v-Math.floor(v)};
export function paintEffect(ctx,w,h,t,energy=0,config={}){
 const {preset='stars',intensity=.55,speed=1,color='#b99aff',seed=17}=config;
 if(preset==='none'||intensity<=0)return;
 const amount=Math.max(0,Math.min(1,intensity)),clock=t*speed;ctx.save();ctx.globalAlpha=amount;ctx.strokeStyle=color;ctx.fillStyle=color;
 if(preset==='stars'||preset==='embers'){
  const count=preset==='stars'?100:75;
  for(let i=0;i<count;i++){const a=unit(i+seed),b=unit(i+seed+177),c=unit(i+seed+339);let x=a*w,y=((b-clock*(.015+c*.045))%1+1)%1*h;const r=(.5+c*2.3)*(1+Math.min(1,energy)*.7)*w/900;ctx.globalAlpha=amount*(.2+.8*c);ctx.fillStyle=preset==='embers'?(i%3?'#ff9954':'#ffe3a4'):color;if(preset==='embers')x+=Math.sin(clock+a*12)*w*.025;ctx.beginPath();ctx.arc(x,y,Math.max(.4,r),0,Math.PI*2);ctx.fill()}
 }else if(preset==='rain'){
  ctx.lineWidth=Math.max(.7,w/1000);for(let i=0;i<100;i++){const a=unit(i+seed),b=unit(i+seed+71),c=unit(i+seed+202);const y=((b+clock*(.35+c*.45))%1)*h,x=(a*w+y*.12)%(w*1.03);ctx.globalAlpha=amount*(.15+c*.55);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+w*.005,y+h*(.015+c*.025));ctx.stroke()}
 }else if(preset==='glitch'){
  const tick=Math.floor(clock*5);for(let i=0;i<5;i++){const r=unit(tick+i+seed);if(r>.65){const y=unit(tick*4+i)*h;ctx.globalAlpha=amount*.22;ctx.fillStyle=i%2?'#43dfef':'#f276d6';ctx.fillRect(unit(i+tick)*w*.3,y,w*(.3+r*.7),Math.max(1,h*.004*r))}}
 }else if(preset==='grain'){
  const tick=Math.floor(clock*12);ctx.fillStyle='#ffffff';for(let i=0;i<500;i++){ctx.globalAlpha=amount*.13;ctx.fillRect(unit(i+tick*103+seed)*w,unit(i+tick*109+seed+5)*h,Math.max(1,w/700),Math.max(1,w/700))}ctx.globalAlpha=amount*.12;ctx.fillStyle='#000000';for(let y=0;y<h;y+=6)ctx.fillRect(0,y,w,1)
 }
 ctx.restore();
}
export function decodeGif(buffer,makeCanvas=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c}){
 const gif=parseGIF(buffer),w=gif.lsd.width,h=gif.lsd.height,images=gif.frames.filter(f=>f.image);
 if(!images.length||images.length>120||w<1||h<1||w>1024||h>1024||w*h*images.length>12000000)throw Error('GIF is too large to animate safely. Use up to 120 frames, 1024px dimensions, and a shorter/smaller GIF.');
 for(const f of images){const d=f.image.descriptor;if(d.width<1||d.height<1||d.width>w||d.height>h||d.left+d.width>w||d.top+d.height>h)throw Error('GIF frame dimensions exceed its logical canvas.')}
 const decoded=decompressFrames(gif,true),composite=makeCanvas(w,h),ctx=composite.getContext('2d'),frames=[];let prior=null,saved=null,total=0;
 for(const f of decoded){
  if(prior?.disposalType===2){ctx.clearRect(prior.dims.left,prior.dims.top,prior.dims.width,prior.dims.height)}
  if(prior?.disposalType===3&&saved)ctx.putImageData(saved,0,0);
  saved=f.disposalType===3?ctx.getImageData(0,0,w,h):null;
  const patch=makeCanvas(f.dims.width,f.dims.height),pc=patch.getContext('2d'),data=pc.createImageData(f.dims.width,f.dims.height);data.data.set(f.patch);pc.putImageData(data,0,0);ctx.drawImage(patch,f.dims.left,f.dims.top);
  const snapshot=makeCanvas(w,h);snapshot.getContext('2d').drawImage(composite,0,0);const delay=Math.max(20,f.delay||100)/1000;frames.push({image:snapshot,start:total,end:total+delay});total+=delay;prior=f;
 }
 return {width:w,height:h,duration:total,frames,at(time){const phase=((time%total)+total)%total;return (frames.find(f=>phase<f.end)||frames.at(-1)).image}};
}
export function paintOverlay(ctx,w,h,t,overlay,config={}){
 if(!overlay)return;const {opacity=.6,scale=.55,blend='screen',position='center',speed=1}=config;const image=overlay.at?overlay.at(t*speed):overlay.image;const dw=w*scale,dh=dw*overlay.height/overlay.width;let x=(w-dw)/2,y=(h-dh)/2;
 if(position==='full'){const s=Math.max(w/overlay.width,h/overlay.height);const fw=overlay.width*s,fh=overlay.height*s;ctx.save();ctx.globalAlpha=opacity;ctx.globalCompositeOperation=blend;ctx.drawImage(image,(w-fw)/2,(h-fh)/2,fw,fh);ctx.restore();return}
 if(position==='bottom-right'){x=w-dw-w*.04;y=h-dh-h*.1}if(position==='top-right'){x=w-dw-w*.04;y=h*.04}
 ctx.save();ctx.globalAlpha=Math.max(0,Math.min(1,opacity));ctx.globalCompositeOperation=blend;ctx.drawImage(image,x,y,dw,dh);ctx.restore();
}
export async function encodeEffectGif(canvas,config,{seconds=2,fps=12,onProgress=()=>{},color='#b99aff'}={}){
 const {GIFEncoder,quantize,applyPalette}=await import('./vendor/gifenc.js');const gif=GIFEncoder();const ctx=canvas.getContext('2d');const count=Math.round(seconds*fps);
 for(let i=0;i<count;i++){ctx.fillStyle='#000000';ctx.fillRect(0,0,canvas.width,canvas.height);paintEffect(ctx,canvas.width,canvas.height,i/fps,.4,{...config,color});const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;const palette=quantize(data,128);gif.writeFrame(applyPalette(data,palette),canvas.width,canvas.height,{palette,delay:1000/fps,repeat:0});onProgress((i+1)/count);if(i%3===0)await new Promise(r=>setTimeout(r,0))}
 gif.finish();return gif.bytes();
}
