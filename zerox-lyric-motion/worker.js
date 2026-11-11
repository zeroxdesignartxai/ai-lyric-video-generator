import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.3';
env.allowLocalModels=false;
let recognizer;
self.onmessage=async ({data})=>{
 try{
  if(!recognizer)recognizer=await pipeline('automatic-speech-recognition','onnx-community/whisper-base',{device:'wasm',dtype:'q8',progress_callback:p=>self.postMessage({type:'loading',file:p.file,progress:p.progress})});
  const result=await recognizer(data.audio,{return_timestamps:'word',chunk_length_s:25,stride_length_s:5});
  self.postMessage({type:'done',words:(result.chunks||[]).filter(w=>w.timestamp?.[0]!=null).map(w=>({text:w.text.trim(),start:w.timestamp[0],end:w.timestamp[1]??w.timestamp[0]+.4}))});
 }catch(e){self.postMessage({type:'error',message:e.message})}
};
