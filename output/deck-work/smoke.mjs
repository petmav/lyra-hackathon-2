import { Presentation, PresentationFile, column, text, fill, hug, fixed, shape, layers, drawSlideToCtx } from '@oai/artifact-tool';
import { Canvas } from 'skia-canvas';
const p=Presentation.create({slideSize:{width:1920,height:1080}});
const s=p.slides.add();
s.compose(layers({width:fill,height:fill},[
 shape({name:'bg',width:fill,height:fill,fill:'#111827'}),
 column({name:'root',width:fill,height:fill,padding:80,gap:20},[
  text('Hello Deck',{name:'title',width:fill,height:hug,style:{fontSize:80,bold:true,color:'#ffffff'}}),
  text('test',{name:'subtitle',style:{fontSize:36,color:'#67e8f9'}})
 ])
]),{frame:{left:0,top:0,width:1920,height:1080},baseUnit:8});
const b=await PresentationFile.exportPptx(p); await b.save('test.pptx');
const canvas=new Canvas(1920,1080); const ctx=canvas.getContext('2d'); await drawSlideToCtx(s,p,ctx); await canvas.saveAs('test.png');
console.log('done');
