let net = null;
const modelInputSize = 640;
let lastCalledTime;
let fps = 0, accumFps = 0, frameCounter = 0;

const video = document.querySelector("#remote");
const canvas = document.getElementById('canvas');
const context = canvas.getContext('2d');
const offscreenCanvas = document.createElement('canvas');
const fpsMeter = document.getElementById('fps-meter');
const loadingContainer = document.getElementById('div-loading');
const wgpuError = document.getElementById('wgpu-error');
offscreenCanvas.width = modelInputSize;
offscreenCanvas.height = modelInputSize;
const offscreenContext = offscreenCanvas.getContext('2d');

async function main() {
  const configuration = { 'iceServers': [{ 'urls': 'stun:stun.l.google.com:19302' }] }
  const peerConnection = new RTCPeerConnection(configuration);
  peerConnection.addTransceiver('video', { 'direction': 'recvonly' })
  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);
  const res = await fetch(window.videoUrl, {
    body: offer.sdp,
    headers: {
      "Content-Type": "application/sdp"
    }, method: "POST"
  })
  const sdp = await res.text();
  const sdi = new RTCSessionDescription({ type: 'answer', sdp })
  peerConnection.ontrack = (ev) => {
    video.srcObject = ev.streams[0];
    video.onloadedmetadata = function() {
      canvas.width = video.clientWidth;
      canvas.height = video.clientHeight;
    }
    requestAnimationFrame(processFrame);
  }
  await peerConnection.setRemoteDescription(sdi)
}

async function processFrame() {
  if (video.videoWidth == 0 || video.videoHeight == 0 || video.readyState < 2) {
    console.log("Video not ready - width:", video.videoWidth, "height:", video.videoHeight, "readyState:", video.readyState);
    requestAnimationFrame(processFrame);
    return;
  }

  if (!lastCalledTime) {
    lastCalledTime = performance.now();
    fps = 0;
  } else {
    const now = performance.now();
    var delta = (now - lastCalledTime) / 1000.0;
    lastCalledTime = now;
    accumFps += 1 / delta;

    if (frameCounter++ >= 10) {
      fps = accumFps / frameCounter;
      frameCounter = 0;
      accumFps = 0;
      fpsMeter.innerText = `FPS: ${fps.toFixed(1)}`
    }
  }

  const videoAspectRatio = video.videoWidth / video.videoHeight;
  let targetWidth, targetHeight;

  if (videoAspectRatio > 1) {
    targetWidth = modelInputSize;
    targetHeight = modelInputSize / videoAspectRatio;
  } else {
    targetHeight = modelInputSize;
    targetWidth = modelInputSize * videoAspectRatio;
  }

  const offsetX = (modelInputSize - targetWidth) / 2;
  const offsetY = (modelInputSize - targetHeight) / 2;
  offscreenContext.fillRect(0, 0, modelInputSize, modelInputSize);
  offscreenContext.drawImage(video, offsetX, offsetY, targetWidth, targetHeight);
  const boxes = await detectObjectsOnFrame(offscreenContext);
  const validBoxes = [];
  for (let i = 0; i < boxes.length; i += 6)
    if (boxes[i + 4] > 0) validBoxes.push([boxes[i], boxes[i + 1], boxes[i + 2], boxes[i + 3], boxes[i + 5]]);
  drawBoxes(offscreenCanvas, validBoxes, targetWidth, targetHeight, offsetX, offsetY);
  requestAnimationFrame(processFrame);
}


function drawBoxes(offscreenCanvas, boxes, targetWidth, targetHeight, offsetX, offsetY) {
  const ctx = document.querySelector("canvas").getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.lineWidth = 3;
  ctx.font = "30px serif";
  const scaleX = canvas.width / targetWidth;
  const scaleY = canvas.height / targetHeight;

  boxes.forEach(([x1, y1, x2, y2, classIndex]) => {
    const label = yolo_classes[classIndex];
    const color = classColors[classIndex];
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    const adjustedX1 = (x1 - offsetX) * scaleX;
    const adjustedY1 = (y1 - offsetY) * scaleY;
    const adjustedX2 = (x2 - offsetX) * scaleX;
    const adjustedY2 = (y2 - offsetY) * scaleY;
    const boxWidth = adjustedX2 - adjustedX1;
    const boxHeight = adjustedY2 - adjustedY1;
    ctx.strokeRect(adjustedX1, adjustedY1, boxWidth, boxHeight);
    const textWidth = ctx.measureText(label).width;
    ctx.fillRect(adjustedX1, adjustedY1 - 25, textWidth + 10, 25);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(label, adjustedX1 + 5, adjustedY1 - 7);
  });
}

async function detectObjectsOnFrame(offscreenContext) {
  if (!net) {
    let device = await getDevice();
    if (!device) {
      wgpuError.style.display = "block";
      loadingContainer.style.display = "none";
    }
    net = await yolov8.load(device, "./static/net.safetensors");
    loadingContainer.style.display = "none";
  }
  let start = performance.now();
  const [input, img_width, img_height] = await prepareInput(offscreenContext);

  start = performance.now();
  const output = await net(new Float32Array(input));

  return output[0];
}

async function prepareInput(offscreenContext) {
  return new Promise(resolve => {
    const [img_width, img_height] = [modelInputSize, modelInputSize]
    const imgData = offscreenContext.getImageData(0, 0, modelInputSize, modelInputSize);
    const pixels = imgData.data;
    const red = [], green = [], blue = [];

    // Debug: Check if we're getting actual image data
    let hasNonZeroPixels = false;
    for (let i = 0; i < Math.min(100, pixels.length); i += 4) {
      if (pixels[i] > 0 || pixels[i + 1] > 0 || pixels[i + 2] > 0) {
        hasNonZeroPixels = true;
        break;
      }
    }

    for (let index = 0; index < pixels.length; index += 4) {
      red.push(pixels[index] / 255.0);
      green.push(pixels[index + 1] / 255.0);
      blue.push(pixels[index + 2] / 255.0);
    }
    const input = [...red, ...green, ...blue];
    resolve([input, img_width, img_height])
  })
}

const getDevice = async () => {
  if (!navigator.gpu) return false;
  const adapter = await navigator.gpu.requestAdapter();
  return await adapter.requestDevice();
};

function processOutput(output, img_width, img_height) {
  let boxes = [];
  const numPredictions = Math.pow(modelInputSize / 32, 2) * 21;
  for (let index = 0; index < numPredictions; index++) {
    const [class_id, prob] = [...Array(yolo_classes.length).keys()]
      .map(col => [col, output[numPredictions * (col + 4) + index]])
      .reduce((accum, item) => item[1] > accum[1] ? item : accum, [0, 0]);

    // if (prob < 0.15) continue; // Lower threshold to see if we get any detections
    const label = yolo_classes[class_id];
    const xc = output[index];
    const yc = output[numPredictions + index];
    const w = output[2 * numPredictions + index];
    const h = output[3 * numPredictions + index];
    const x1 = (xc - w / 2) / modelInputSize * img_width;
    const y1 = (yc - h / 2) / modelInputSize * img_height;
    const x2 = (xc + w / 2) / modelInputSize * img_width;
    const y2 = (yc + h / 2) / modelInputSize * img_height;
    boxes.push([x1, y1, x2, y2, label, prob]);
  }

  boxes = boxes.sort((box1, box2) => box2[5] - box1[5])
  const result = [];
  while (boxes.length > 0) {
    result.push(boxes[0]);
    boxes = boxes.filter(box => iou(boxes[0], box) < 0.7);
  }
  return result;
}

function iou(box1, box2) {
  return intersection(box1, box2) / union(box1, box2);
}

function union(box1, box2) {
  const [box1_x1, box1_y1, box1_x2, box1_y2] = box1;
  const [box2_x1, box2_y1, box2_x2, box2_y2] = box2;
  const box1_area = (box1_x2 - box1_x1) * (box1_y2 - box1_y1)
  const box2_area = (box2_x2 - box2_x1) * (box2_y2 - box2_y1)
  return box1_area + box2_area - intersection(box1, box2)
}

function intersection(box1, box2) {
  const [box1_x1, box1_y1, box1_x2, box1_y2] = box1;
  const [box2_x1, box2_y1, box2_x2, box2_y2] = box2;
  const x1 = Math.max(box1_x1, box2_x1);
  const y1 = Math.max(box1_y1, box2_y1);
  const x2 = Math.min(box1_x2, box2_x2);
  const y2 = Math.min(box1_y2, box2_y2);
  return (x2 - x1) * (y2 - y1)
}

const yolo_classes = [
  'Andamio', 'Animal', 'Aplanadora', 'Arbol', 'Barril', 'Block', 'Cabina', 'Cables', 'Camion', 'CamionDeRiego', 'CamionVolquete', 'Carga', 'Carretilla', 'Casco', 'Castillo', 'Cementadora', 'Chaleco', 'Charca', 'Cimbra', 'Colado', 'Columna', 'Construccion', 'Contenedor', 'Cubeta', 'Descarga', 'Edificio', 'Escalera', 'Espectacular', 'Excavadora', 'Excavar', 'Follaje', 'Grua', 'Herramienta', 'Lona', 'Material', 'Medir', 'Monticulo', 'Motoconformadora', 'Muro', 'Pala', 'Polines', 'Poste', 'Registro', 'Reja', 'Residuos', 'Retrete', 'Riego', 'Tapa', 'Techo', 'Tinaco', 'Toldo', 'TorreDeElectricidad', 'Trabajador', 'Tractor', 'Tuberia', 'Varilla', 'Vehiculo', 'Vigas', 'Zanja'
];

function generateColors(numColors) {
  const colors = [];
  for (let i = 0; i < 360; i += 360 / numColors) {
    colors.push(`hsl(${i}, 100%, 50%)`);
  }
  return colors;
}

const classColors = generateColors(yolo_classes.length);
// Wait for DOM to be ready before starting
window.addEventListener('load', () => {
  console.log("Starting WebRTC connection...");
  main().catch(err => {
    console.error("Error initializing WebRTC:", err);
  });
});
