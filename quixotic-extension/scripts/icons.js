// Draws the orange "Q" toolbar icon as PNGs with plain Node (no image tools). Usage: node scripts/icons.js
import {writeFileSync,mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {crc32,deflateSync} from 'node:zlib';

export const ICON_SIZES=[16,32,48,128];
const SS=4;   // 4x4 samples per pixel for smooth edges

// Signed distance helpers in unit coordinates (0..1).
function inRoundedSquare(x,y,r){const dx=Math.max(Math.abs(x-.5)-(.5-r),0),dy=Math.max(Math.abs(y-.5)-(.5-r),0);return dx*dx+dy*dy<=r*r;}
function inQ(x,y){
  const d=Math.hypot(x-.5,y-.47);
  if(d<=.27&&d>=.17) return true;                                   // ring
  const ax=.56,ay=.58,bx=.76,by=.78,t=Math.max(0,Math.min(1,((x-ax)*(bx-ax)+(y-ay)*(by-ay))/((bx-ax)**2+(by-ay)**2)));
  return Math.hypot(x-(ax+t*(bx-ax)),y-(ay+t*(by-ay)))<=.055;        // tail
}

// RGBA pixels: orange gradient badge (#ff8a3d -> #e2501a) with a white Q.
export function drawIcon(size){
  const px=Buffer.alloc(size*size*4);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    let badge=0,q=0;
    for(let sy=0;sy<SS;sy++)for(let sx=0;sx<SS;sx++){
      const u=(x+(sx+.5)/SS)/size,v=(y+(sy+.5)/SS)/size;
      if(inRoundedSquare(u,v,.24)){badge++;if(inQ(u,v)) q++;}
    }
    const n=SS*SS,t=(x+y)/(2*size),k=q/Math.max(badge,1);
    const o=[255+(226-255)*t,138+(80-138)*t,61+(26-61)*t];
    const i=(y*size+x)*4;
    for(let c=0;c<3;c++) px[i+c]=Math.round(o[c]+(255-o[c])*k);
    px[i+3]=Math.round(255*badge/n);
  }
  return px;
}

function chunk(type,data){
  const len=Buffer.alloc(4),body=Buffer.concat([Buffer.from(type,'ascii'),data]),crc=Buffer.alloc(4);
  len.writeUInt32BE(data.length);crc.writeUInt32BE(crc32(body)>>>0);
  return Buffer.concat([len,body,crc]);
}

export function encodePng(size,rgba){
  const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(size,0);ihdr.writeUInt32BE(size,4);ihdr[8]=8;ihdr[9]=6;
  const raw=Buffer.alloc(size*(size*4+1));
  for(let y=0;y<size;y++) rgba.copy(raw,y*(size*4+1)+1,y*size*4,(y+1)*size*4);   // filter 0 per row
  return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',ihdr),chunk('IDAT',deflateSync(raw,{level:9})),chunk('IEND',Buffer.alloc(0))]);
}

if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])){
  const dir=fileURLToPath(new URL('../icons/',import.meta.url));mkdirSync(dir,{recursive:true});
  for(const s of ICON_SIZES) writeFileSync(dir+`icon${s}.png`,encodePng(s,drawIcon(s)));
  console.log(`Wrote ${ICON_SIZES.length} icons to ${dir}`);
}
