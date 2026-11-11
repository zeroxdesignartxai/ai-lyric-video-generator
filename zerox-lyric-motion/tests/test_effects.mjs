import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createCanvas} from '@napi-rs/canvas';
import {PRESETS,paintEffect,decodeGif,paintOverlay,encodeEffectGif} from '../effects.js';
const c=createCanvas(480,270),ctx=c.getContext('2d');
for(const preset of PRESETS.filter(s=>s!=='none')){
 ctx.fillStyle='black';ctx.fillRect(0,0,480,270);paintEffect(ctx,480,270,.8,.7,{preset,intensity:.8});const a=c.toBuffer('image/png');
 ctx.fillStyle='black';ctx.fillRect(0,0,480,270);paintEffect(ctx,480,270,1.8,.7,{preset,intensity:.8});const b=c.toBuffer('image/png');assert(!a.equals(b),preset+' must animate');fs.writeFileSync(`./${preset}.png`,b);console.log('PASS animated',preset)
}
const bytes=fs.readFileSync('./overlay.gif');const gif=decodeGif(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),createCanvas);
assert.equal(gif.frames.length,8);assert(gif.at(.05)!==gif.at(.15));assert(gif.at(.05)===gif.at(.85));
for(let i=0;i<gif.frames.length;i++)fs.writeFileSync(`./decoded-${i}.png`,gif.frames[i].image.toBuffer('image/png'));
console.log('PASS GIF animation, timing and looping');
ctx.fillStyle='black';ctx.fillRect(0,0,480,270);paintOverlay(ctx,480,270,.15,gif,{opacity:.75,scale:.6,blend:'screen',position:'center'});fs.writeFileSync('./composite.png',c.toBuffer('image/png'));console.log('PASS GIF compositing');
const output=await encodeEffectGif(c,{preset:'embers',intensity:.8},{seconds:2,fps:12});fs.writeFileSync('./generated-embers.gif',output);assert.equal(new TextDecoder().decode(output.slice(0,6)),'GIF89a');console.log('PASS GIF encoder',output.length,'bytes');
