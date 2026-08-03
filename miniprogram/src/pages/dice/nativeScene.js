const DICE_COUNT = 5;
const DIE_HALF = 0.4;
const FLOOR_Y = DIE_HALF + 0.04;
const CUP_SAFE_RADIUS = 1.66;
const DICE_SEPARATION = 0.86;
const PHYSICS_STEP = 1 / 120;
const MAX_PHYSICS_STEPS = 6;
const MIN_ROLL_DURATION = 1750;
const MAX_ROLL_DURATION = 3400;
const SLEEP_FRAME_TARGET = 14;
const SLEEP_LINEAR_SPEED = 0.42;
const SLEEP_ANGULAR_SPEED = 1.15;

const FACE_VALUES = [
  { axis: 1, side: 1, value: 1, uAxis: 2, vAxis: 0 },
  { axis: 1, side: -1, value: 6, uAxis: 0, vAxis: 2 },
  { axis: 2, side: 1, value: 2, uAxis: 0, vAxis: 1 },
  { axis: 2, side: -1, value: 5, uAxis: 1, vAxis: 0 },
  { axis: 0, side: 1, value: 3, uAxis: 1, vAxis: 2 },
  { axis: 0, side: -1, value: 4, uAxis: 2, vAxis: 1 },
];

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function normalize3(vector) {
  const length = Math.hypot(vector[0], vector[1], vector[2]) || 1;
  return [vector[0] / length, vector[1] / length, vector[2] / length];
}

function cross3(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function dot3(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function mat4Multiply(a, b) {
  const out = new Float32Array(16);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      out[column * 4 + row] =
        a[row] * b[column * 4] +
        a[4 + row] * b[column * 4 + 1] +
        a[8 + row] * b[column * 4 + 2] +
        a[12 + row] * b[column * 4 + 3];
    }
  }
  return out;
}

function perspective(fieldOfView, aspect, near, far) {
  const f = 1 / Math.tan(fieldOfView / 2);
  const range = 1 / (near - far);
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (near + far) * range, -1,
    0, 0, near * far * range * 2, 0,
  ]);
}

function lookAt(eye, target, up) {
  const z = normalize3([eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]]);
  const x = normalize3(cross3(up, z));
  const y = cross3(z, x);
  return new Float32Array([
    x[0], y[0], z[0], 0,
    x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0,
    -dot3(x, eye), -dot3(y, eye), -dot3(z, eye), 1,
  ]);
}

function quatNormalize(q) {
  const length = Math.hypot(q[0], q[1], q[2], q[3]) || 1;
  q[0] /= length;
  q[1] /= length;
  q[2] /= length;
  q[3] /= length;
  return q;
}

function quatMultiply(a, b) {
  return [
    a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
    a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
    a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
    a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2],
  ];
}

function updateQuaternion(quaternion, angularVelocity, delta) {
  const speed = Math.hypot(...angularVelocity);
  if (speed < 0.0001) return;
  const angle = speed * delta;
  const halfAngle = angle / 2;
  const sine = Math.sin(halfAngle) / speed;
  const step = [
    angularVelocity[0] * sine,
    angularVelocity[1] * sine,
    angularVelocity[2] * sine,
    Math.cos(halfAngle),
  ];
  const next = quatMultiply(step, quaternion);
  quaternion.splice(0, 4, ...quatNormalize(next));
}

function rotateVector(quaternion, vector) {
  const qVector = [vector[0], vector[1], vector[2], 0];
  const inverse = [-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3]];
  return quatMultiply(quatMultiply(quaternion, qVector), inverse).slice(0, 3);
}

function modelMatrix(position, quaternion, scale = [1, 1, 1]) {
  const [x, y, z, w] = quaternion;
  const x2 = x + x;
  const y2 = y + y;
  const z2 = z + z;
  const xx = x * x2;
  const xy = x * y2;
  const xz = x * z2;
  const yy = y * y2;
  const yz = y * z2;
  const zz = z * z2;
  const wx = w * x2;
  const wy = w * y2;
  const wz = w * z2;
  return new Float32Array([
    (1 - (yy + zz)) * scale[0], (xy + wz) * scale[0], (xz - wy) * scale[0], 0,
    (xy - wz) * scale[1], (1 - (xx + zz)) * scale[1], (yz + wx) * scale[1], 0,
    (xz + wy) * scale[2], (yz - wx) * scale[2], (1 - (xx + yy)) * scale[2], 0,
    position[0], position[1], position[2], 1,
  ]);
}

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const reason = gl.getShaderInfoLog(shader) || "unknown shader error";
    gl.deleteShader(shader);
    throw new Error(reason);
  }
  return shader;
}

function createProgram(gl) {
  const vertexSource = `
    attribute vec3 aPosition;
    attribute vec3 aNormal;
    attribute vec2 aUv;
    attribute float aFace;
    uniform mat4 uViewProjection;
    uniform mat4 uModel;
    varying vec3 vNormal;
    varying vec3 vWorld;
    varying vec2 vUv;
    varying float vFace;
    void main() {
      vec4 world = uModel * vec4(aPosition, 1.0);
      vWorld = world.xyz;
      vNormal = normalize(mat3(uModel) * aNormal);
      vUv = aUv;
      vFace = aFace;
      gl_Position = uViewProjection * world;
    }
  `;
  const fragmentSource = `
    precision mediump float;
    varying vec3 vNormal;
    varying vec3 vWorld;
    varying vec2 vUv;
    varying float vFace;
    uniform vec3 uColor;
    uniform vec3 uEye;
    uniform float uDice;
    uniform float uMaterial;
    uniform float uGlow;

    float grain(vec2 point) {
      return fract(sin(dot(point, vec2(12.9898, 78.233))) * 43758.5453);
    }

    float dotMark(vec2 uv, vec2 center) {
      return 1.0 - smoothstep(0.105, 0.135, distance(uv, center));
    }
    float pipMask(float face, vec2 uv) {
      float m = 0.0;
      vec2 tl = vec2(0.28, 0.72);
      vec2 tr = vec2(0.72, 0.72);
      vec2 ml = vec2(0.28, 0.50);
      vec2 mr = vec2(0.72, 0.50);
      vec2 bl = vec2(0.28, 0.28);
      vec2 br = vec2(0.72, 0.28);
      vec2 cc = vec2(0.50, 0.50);
      if (face < 1.5) m = dotMark(uv, cc);
      else if (face < 2.5) m = max(dotMark(uv, tl), dotMark(uv, br));
      else if (face < 3.5) m = max(max(dotMark(uv, tl), dotMark(uv, cc)), dotMark(uv, br));
      else if (face < 4.5) m = max(max(dotMark(uv, tl), dotMark(uv, tr)), max(dotMark(uv, bl), dotMark(uv, br)));
      else if (face < 5.5) m = max(max(max(dotMark(uv, tl), dotMark(uv, tr)), dotMark(uv, cc)), max(dotMark(uv, bl), dotMark(uv, br)));
      else m = max(max(max(dotMark(uv, tl), dotMark(uv, ml)), dotMark(uv, bl)), max(max(dotMark(uv, tr), dotMark(uv, mr)), dotMark(uv, br)));
      return m;
    }
    void main() {
      vec3 normal = normalize(vNormal);
      vec3 lightDirection = normalize(vec3(-0.45, 1.0, 0.55));
      vec3 fillDirection = normalize(vec3(0.72, 0.42, -0.58));
      vec3 viewDirection = normalize(uEye - vWorld);
      vec3 halfway = normalize(lightDirection + viewDirection);
      float diffuse = max(dot(normal, lightDirection), 0.0);
      float fill = max(dot(normal, fillDirection), 0.0);
      float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 2.2);
      float shine = pow(max(dot(normal, halfway), 0.0), uDice > 0.5 ? 42.0 : 22.0);
      vec3 color = uColor;
      if (uDice > 0.5) {
        float pip = pipMask(vFace, vUv);
        vec3 pipColor = (vFace < 1.5 || (vFace > 3.5 && vFace < 4.5))
          ? vec3(0.91, 0.035, 0.09)
          : vec3(0.035, 0.22, 0.78);
        color = mix(vec3(0.99, 0.985, 0.95), pipColor, pip);
        color *= 0.70 + diffuse * 0.34 + fill * 0.13;
        color += shine * 0.54 + rim * vec3(0.09, 0.15, 0.24);
        color += vec3(0.035, 0.055, 0.085) * fill;
        color -= pip * 0.05;
      } else if (uMaterial > 1.5 && uMaterial < 2.5) {
        float radius = length(vWorld.xz) / 4.0;
        float fibers = grain(floor(vWorld.xz * 145.0));
        float weave = sin(vWorld.x * 165.0) * sin(vWorld.z * 165.0);
        float spotlight = 1.0 - smoothstep(0.0, 1.0, radius) * 0.34;
        color *= (0.69 + diffuse * 0.27 + fill * 0.08 + fibers * 0.10 + weave * 0.018) * spotlight;
        color += vec3(0.018, 0.15, 0.28) * (1.0 - radius) + shine * 0.12;
      } else if (uMaterial > 2.5 && uMaterial < 3.5) {
        float leather = grain(floor(vec2(atan(vWorld.z, vWorld.x) * 95.0, vWorld.y * 130.0)));
        float vertical = 0.82 + clamp(vWorld.y * 0.08, -0.12, 0.16);
        color *= (0.54 + diffuse * 0.42 + fill * 0.10 + leather * 0.08) * vertical;
        color += shine * 0.34 + rim * vec3(0.12, 0.025, 0.045);
      } else if (uMaterial > 3.5) {
        color *= 0.78 + diffuse * 0.26 + fill * 0.08;
        color += shine * 0.72 + uGlow * color * 1.6;
      } else {
        color *= 0.44 + diffuse * 0.54 + fill * 0.10;
        color += shine * 0.25 + rim * vec3(0.04, 0.14, 0.24);
      }
      color += uGlow * vec3(0.08, 0.46, 0.95);
      float distanceFog = smoothstep(7.0, 13.0, distance(uEye, vWorld));
      color = mix(color, vec3(0.004, 0.009, 0.026), distanceFog * 0.16);
      color = pow(max(color, vec3(0.0)), vec3(0.94));
      gl_FragColor = vec4(color, 1.0);
    }
  `;
  const program = gl.createProgram();
  gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER, vertexSource));
  gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(program) || "WebGL program link failed");
  }
  return program;
}

function roundedPoint(point, half, radius) {
  const inner = half - radius;
  const closest = point.map((value) => clamp(value, -inner, inner));
  const offset = point.map((value, index) => value - closest[index]);
  const normal = normalize3(offset);
  return {
    position: closest.map((value, index) => value + normal[index] * radius),
    normal,
  };
}

function createRoundedCubeData(subdivisions = 7) {
  const positions = [];
  const normals = [];
  const uvs = [];
  const faces = [];
  const indices = [];
  FACE_VALUES.forEach((face) => {
    const start = positions.length / 3;
    for (let row = 0; row <= subdivisions; row += 1) {
      for (let column = 0; column <= subdivisions; column += 1) {
        const u = column / subdivisions;
        const v = row / subdivisions;
        const point = [0, 0, 0];
        point[face.axis] = DIE_HALF * face.side;
        point[face.uAxis] = (u * 2 - 1) * DIE_HALF;
        point[face.vAxis] = (v * 2 - 1) * DIE_HALF;
        const rounded = roundedPoint(point, DIE_HALF, 0.1);
        positions.push(...rounded.position);
        normals.push(...rounded.normal);
        uvs.push(u, v);
        faces.push(face.value);
      }
    }
    const stride = subdivisions + 1;
    for (let row = 0; row < subdivisions; row += 1) {
      for (let column = 0; column < subdivisions; column += 1) {
        const a = start + row * stride + column;
        const b = a + 1;
        const c = a + stride;
        const d = c + 1;
        indices.push(a, b, d, a, d, c);
      }
    }
  });
  return { positions, normals, uvs, faces, indices };
}

function createCylinderData(topRadius, bottomRadius, height, segments = 56, capBottom = true) {
  const positions = [];
  const normals = [];
  const uvs = [];
  const faces = [];
  const indices = [];
  for (let index = 0; index <= segments; index += 1) {
    const angle = (index / segments) * Math.PI * 2;
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    positions.push(cosine * bottomRadius, -height / 2, sine * bottomRadius);
    positions.push(cosine * topRadius, height / 2, sine * topRadius);
    const slope = (bottomRadius - topRadius) / height;
    const normal = normalize3([cosine, slope, sine]);
    normals.push(...normal, ...normal);
    uvs.push(index / segments, 0, index / segments, 1);
    faces.push(0, 0);
    if (index < segments) {
      const offset = index * 2;
      indices.push(offset, offset + 1, offset + 3, offset, offset + 3, offset + 2);
    }
  }
  const addCap = (y, radius, upward) => {
    const center = positions.length / 3;
    positions.push(0, y, 0);
    normals.push(0, upward ? 1 : -1, 0);
    uvs.push(0.5, 0.5);
    faces.push(0);
    for (let index = 0; index <= segments; index += 1) {
      const angle = (index / segments) * Math.PI * 2;
      positions.push(Math.cos(angle) * radius, y, Math.sin(angle) * radius);
      normals.push(0, upward ? 1 : -1, 0);
      uvs.push(Math.cos(angle) * 0.5 + 0.5, Math.sin(angle) * 0.5 + 0.5);
      faces.push(0);
      if (index < segments) {
        if (upward) indices.push(center, center + index + 2, center + index + 1);
        else indices.push(center, center + index + 1, center + index + 2);
      }
    }
  };
  addCap(height / 2, topRadius, true);
  if (capBottom) addCap(-height / 2, bottomRadius, false);
  return { positions, normals, uvs, faces, indices };
}

function createLatheData(profile, segments = 72) {
  const positions = [];
  const normals = [];
  const uvs = [];
  const faces = [];
  const indices = [];
  for (let row = 0; row < profile.length; row += 1) {
    const previous = profile[Math.max(0, row - 1)];
    const next = profile[Math.min(profile.length - 1, row + 1)];
    const deltaRadius = next[0] - previous[0];
    const deltaY = next[1] - previous[1];
    for (let column = 0; column <= segments; column += 1) {
      const angle = (column / segments) * Math.PI * 2;
      const cosine = Math.cos(angle);
      const sine = Math.sin(angle);
      const [radius, y] = profile[row];
      positions.push(cosine * radius, y, sine * radius);
      const normal = radius < 0.001
        ? [0, 1, 0]
        : normalize3([deltaY * cosine, -deltaRadius, deltaY * sine]);
      normals.push(...normal);
      uvs.push(column / segments, row / (profile.length - 1));
      faces.push(0);
    }
  }
  const stride = segments + 1;
  for (let row = 0; row < profile.length - 1; row += 1) {
    for (let column = 0; column < segments; column += 1) {
      const a = row * stride + column;
      const b = a + 1;
      const c = a + stride;
      const d = c + 1;
      indices.push(a, c, d, a, d, b);
    }
  }
  return { positions, normals, uvs, faces, indices };
}

function createTorusData(majorRadius, minorRadius, radialSegments = 64, tubeSegments = 12) {
  const positions = [];
  const normals = [];
  const uvs = [];
  const faces = [];
  const indices = [];
  for (let ring = 0; ring <= radialSegments; ring += 1) {
    const u = (ring / radialSegments) * Math.PI * 2;
    const cosineU = Math.cos(u);
    const sineU = Math.sin(u);
    for (let tube = 0; tube <= tubeSegments; tube += 1) {
      const v = (tube / tubeSegments) * Math.PI * 2;
      const cosineV = Math.cos(v);
      const sineV = Math.sin(v);
      const radius = majorRadius + minorRadius * cosineV;
      positions.push(radius * cosineU, minorRadius * sineV, radius * sineU);
      normals.push(cosineU * cosineV, sineV, sineU * cosineV);
      uvs.push(ring / radialSegments, tube / tubeSegments);
      faces.push(0);
    }
  }
  const stride = tubeSegments + 1;
  for (let ring = 0; ring < radialSegments; ring += 1) {
    for (let tube = 0; tube < tubeSegments; tube += 1) {
      const a = ring * stride + tube;
      const b = a + stride;
      const c = b + 1;
      const d = a + 1;
      indices.push(a, b, c, a, c, d);
    }
  }
  return { positions, normals, uvs, faces, indices };
}

function uploadMesh(gl, data) {
  const attributes = {};
  const upload = (name, values) => {
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(values), gl.STATIC_DRAW);
    attributes[name] = buffer;
  };
  upload("position", data.positions);
  upload("normal", data.normals);
  upload("uv", data.uvs);
  upload("face", data.faces);
  const indexBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(data.indices), gl.STATIC_DRAW);
  return { attributes, indexBuffer, count: data.indices.length };
}

function bindMesh(gl, locations, mesh) {
  const bind = (location, buffer, size) => {
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, size, gl.FLOAT, false, 0, 0);
  };
  bind(locations.position, mesh.attributes.position, 3);
  bind(locations.normal, mesh.attributes.normal, 3);
  bind(locations.uv, mesh.attributes.uv, 2);
  bind(locations.face, mesh.attributes.face, 1);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mesh.indexBuffer);
}

function topFace(quaternion) {
  let best = FACE_VALUES[0];
  let bestY = -Infinity;
  FACE_VALUES.forEach((face) => {
    const normal = [0, 0, 0];
    normal[face.axis] = face.side;
    const y = rotateVector(quaternion, normal)[1];
    if (y > bestY) {
      bestY = y;
      best = face;
    }
  });
  return best.value;
}

function quaternionFromAxisAngle(axis, angle) {
  const halfAngle = angle / 2;
  const sine = Math.sin(halfAngle);
  return [axis[0] * sine, axis[1] * sine, axis[2] * sine, Math.cos(halfAngle)];
}

function settledQuaternion(faceValue, yaw) {
  const baseByFace = {
    1: [0, 0, 0, 1],
    6: quaternionFromAxisAngle([1, 0, 0], Math.PI),
    2: quaternionFromAxisAngle([1, 0, 0], -Math.PI / 2),
    5: quaternionFromAxisAngle([1, 0, 0], Math.PI / 2),
    3: quaternionFromAxisAngle([0, 0, 1], Math.PI / 2),
    4: quaternionFromAxisAngle([0, 0, 1], -Math.PI / 2),
  };
  const yawQuaternion = quaternionFromAxisAngle([0, 1, 0], yaw);
  return quatNormalize(quatMultiply(yawQuaternion, baseByFace[faceValue]));
}

function createSettledSlots() {
  const rotation = randomBetween(0, Math.PI * 2);
  return Array.from({ length: DICE_COUNT }, (_, index) => {
    const angle = rotation + (index / DICE_COUNT) * Math.PI * 2 + randomBetween(-0.02, 0.02);
    const radius = randomBetween(1.08, 1.12);
    return [Math.cos(angle) * radius, FLOOR_Y, Math.sin(angle) * radius];
  });
}

function getPlacementMetrics(dice) {
  let minSeparation = Infinity;
  let maxTilt = 0;
  for (let left = 0; left < dice.length; left += 1) {
    const face = FACE_VALUES.find((item) => item.value === dice[left].result);
    const normal = [0, 0, 0];
    normal[face.axis] = face.side;
    maxTilt = Math.max(maxTilt, 1 - rotateVector(dice[left].quaternion, normal)[1]);
    for (let right = left + 1; right < dice.length; right += 1) {
      minSeparation = Math.min(
        minSeparation,
        Math.hypot(
          dice[right].position[0] - dice[left].position[0],
          dice[right].position[2] - dice[left].position[2],
        ),
      );
    }
  }
  return { minSeparation, maxTilt };
}

function createDie(index) {
  const angle = (index / DICE_COUNT) * Math.PI * 2;
  return {
    position: [Math.cos(angle) * 0.85, FLOOR_Y, Math.sin(angle) * 0.85],
    velocity: [0, 0, 0],
    angularVelocity: [0, 0, 0],
    quaternion: quatNormalize([
      randomBetween(-1, 1),
      randomBetween(-1, 1),
      randomBetween(-1, 1),
      randomBetween(-1, 1),
    ]),
    result: 1,
  };
}

function constrainToCup(die) {
  const radius = Math.hypot(die.position[0], die.position[2]);
  if (radius <= CUP_SAFE_RADIUS) return 0;
  const nx = die.position[0] / radius;
  const nz = die.position[2] / radius;
  die.position[0] = nx * CUP_SAFE_RADIUS;
  die.position[2] = nz * CUP_SAFE_RADIUS;
  const outward = die.velocity[0] * nx + die.velocity[2] * nz;
  if (outward > 0) {
    die.velocity[0] -= outward * nx * 1.72;
    die.velocity[2] -= outward * nz * 1.72;
  }
  return Math.abs(outward);
}

function simulate(dice, delta) {
  let impact = 0;
  dice.forEach((die) => {
    die.velocity[1] -= 9.4 * delta;
    for (let axis = 0; axis < 3; axis += 1) die.position[axis] += die.velocity[axis] * delta;
    updateQuaternion(die.quaternion, die.angularVelocity, delta);
    if (die.position[1] < FLOOR_Y) {
      impact = Math.max(impact, Math.abs(die.velocity[1]));
      die.position[1] = FLOOR_Y;
      die.velocity[1] = Math.abs(die.velocity[1]) < 0.48 ? 0 : Math.abs(die.velocity[1]) * 0.38;
      die.velocity[0] *= 0.925;
      die.velocity[2] *= 0.925;
      die.angularVelocity = die.angularVelocity.map((value) => value * 0.885);
    }
    // Exponential damping gives the same feel on 30 Hz and 60 Hz devices.
    const linearDamping = Math.pow(0.988, delta * 120);
    const angularDamping = Math.pow(0.992, delta * 120);
    die.velocity[0] *= linearDamping;
    die.velocity[2] *= linearDamping;
    die.angularVelocity = die.angularVelocity.map((value) => value * angularDamping);
    impact = Math.max(impact, constrainToCup(die));
  });
  for (let left = 0; left < dice.length; left += 1) {
    for (let right = left + 1; right < dice.length; right += 1) {
      const a = dice[left];
      const b = dice[right];
      const deltaPosition = [
        b.position[0] - a.position[0],
        b.position[1] - a.position[1],
        b.position[2] - a.position[2],
      ];
      const distance = Math.hypot(...deltaPosition) || 0.001;
      if (distance >= DICE_SEPARATION) continue;
      const normal = deltaPosition.map((value) => value / distance);
      const relative = [
        b.velocity[0] - a.velocity[0],
        b.velocity[1] - a.velocity[1],
        b.velocity[2] - a.velocity[2],
      ];
      const closing = dot3(relative, normal);
      if (closing < 0) {
        const impulse = -closing * 0.72;
        for (let axis = 0; axis < 3; axis += 1) {
          a.velocity[axis] -= normal[axis] * impulse;
          b.velocity[axis] += normal[axis] * impulse;
        }
        impact = Math.max(impact, impulse);
      }
    }
  }
  return impact;
}

function diceAreSleeping(dice) {
  return dice.every((die) => {
    const linear = Math.hypot(...die.velocity);
    const angular = Math.hypot(...die.angularVelocity);
    return (
      die.position[1] <= FLOOR_Y + 0.015 &&
      linear <= SLEEP_LINEAR_SPEED &&
      angular <= SLEEP_ANGULAR_SPEED
    );
  });
}

export function createNativeDiceScene({ canvas, width, height, onImpact }) {
  const gl = canvas.getContext("webgl", {
    antialias: true,
    alpha: false,
    depth: true,
    preserveDrawingBuffer: false,
  });
  if (!gl) throw new Error("当前微信版本没有提供 WebGL，请更新微信后重试");

  // A capped pixel ratio keeps fill-rate predictable on high-DPI phones while
  // preserving the rounded edges and pips at mini-program canvas sizes.
  const pixelRatio = Math.min(1.75, globalThis.wx?.getWindowInfo?.().pixelRatio || 1);
  canvas.width = Math.floor(width * pixelRatio);
  canvas.height = Math.floor(height * pixelRatio);
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.enable(gl.DEPTH_TEST);
  gl.enable(gl.CULL_FACE);
  gl.cullFace(gl.BACK);
  gl.clearColor(0.002, 0.005, 0.018, 1);

  const program = createProgram(gl);
  gl.useProgram(program);
  const attributes = {
    position: gl.getAttribLocation(program, "aPosition"),
    normal: gl.getAttribLocation(program, "aNormal"),
    uv: gl.getAttribLocation(program, "aUv"),
    face: gl.getAttribLocation(program, "aFace"),
  };
  const uniforms = {
    viewProjection: gl.getUniformLocation(program, "uViewProjection"),
    model: gl.getUniformLocation(program, "uModel"),
    color: gl.getUniformLocation(program, "uColor"),
    eye: gl.getUniformLocation(program, "uEye"),
    dice: gl.getUniformLocation(program, "uDice"),
    material: gl.getUniformLocation(program, "uMaterial"),
    glow: gl.getUniformLocation(program, "uGlow"),
  };

  const meshes = {
    die: uploadMesh(gl, createRoundedCubeData()),
    table: uploadMesh(gl, createCylinderData(3.82, 4.08, 0.48, 72)),
    felt: uploadMesh(gl, createCylinderData(3.66, 3.72, 0.13, 72)),
    cup: uploadMesh(gl, createLatheData([
      [1.72, -1.25],
      [1.76, -1.16],
      [1.63, -1.04],
      [1.55, -0.48],
      [1.46, 0.50],
      [1.36, 0.96],
      [1.18, 1.16],
      [0.82, 1.27],
      [0.18, 1.31],
      [0.0, 1.31],
    ])),
    tableRing: uploadMesh(gl, createTorusData(3.72, 0.075, 72, 12)),
    cupRim: uploadMesh(gl, createTorusData(1.7, 0.085, 72, 12)),
    cupBand: uploadMesh(gl, createTorusData(1.23, 0.045, 64, 10)),
    shadow: uploadMesh(gl, createCylinderData(0.46, 0.56, 0.025, 28)),
  };
  const eye = [0, 6.5, 7.8];
  const projection = perspective(Math.PI / 4.65, width / height, 0.1, 30);
  const view = lookAt(eye, [0, 0.36, 0], [0, 1, 0]);
  const viewProjection = mat4Multiply(projection, view);
  gl.uniformMatrix4fv(uniforms.viewProjection, false, viewProjection);
  gl.uniform3fv(uniforms.eye, eye);

  const dice = Array.from({ length: DICE_COUNT }, (_, index) => createDie(index));
  const state = {
    disposed: false,
    paused: false,
    rolling: false,
    rollStartedAt: 0,
    lastTime: 0,
    physicsAccumulator: 0,
    physicsSteps: 0,
    sleepFrames: 0,
    settleMs: 0,
    lastImpactAt: 0,
    frameId: null,
    resolveRoll: null,
    cupLift: 0,
    cupOpening: false,
    cupOpenStartedAt: 0,
    resolveOpen: null,
    glow: 0,
    dirty: true,
  };

  const drawMesh = (mesh, model, color, material = 0, glow = 0) => {
    bindMesh(gl, attributes, mesh);
    gl.uniformMatrix4fv(uniforms.model, false, model);
    gl.uniform3fv(uniforms.color, color);
    gl.uniform1f(uniforms.dice, material === 1 ? 1 : 0);
    gl.uniform1f(uniforms.material, material);
    gl.uniform1f(uniforms.glow, glow);
    gl.drawElements(gl.TRIANGLES, mesh.count, gl.UNSIGNED_SHORT, 0);
  };

  const finishRoll = (timestamp) => {
    state.rolling = false;
    state.physicsAccumulator = 0;
    state.settleMs = Math.round(timestamp - state.rollStartedAt);
    const slots = createSettledSlots();
    dice.forEach((die, index) => {
      // Preserve the physically produced top face, then place every die into
      // an independent slot and level that face with the table. The cup is
      // still closed here, so the small settling correction is never visible.
      die.result = topFace(die.quaternion);
      die.position = slots[index];
      die.velocity = [0, 0, 0];
      die.angularVelocity = [0, 0, 0];
      die.quaternion = settledQuaternion(die.result, randomBetween(0, Math.PI * 2));
    });
    const resolve = state.resolveRoll;
    state.resolveRoll = null;
    state.dirty = true;
    resolve?.(dice.map((die) => die.result));
  };

  const render = (timestamp) => {
    if (state.disposed || state.paused) return;
    const delta = clamp((timestamp - (state.lastTime || timestamp)) / 1000, 0, 0.034);
    state.lastTime = timestamp;
    let shouldDraw = state.dirty;
    if (state.rolling) {
      if (!state.rollStartedAt) state.rollStartedAt = timestamp;
      const elapsed = timestamp - state.rollStartedAt;
      let impact = 0;
      state.physicsAccumulator = Math.min(
        state.physicsAccumulator + delta,
        PHYSICS_STEP * MAX_PHYSICS_STEPS,
      );
      let stepsThisFrame = 0;
      while (state.physicsAccumulator >= PHYSICS_STEP && stepsThisFrame < MAX_PHYSICS_STEPS) {
        impact = Math.max(impact, simulate(dice, PHYSICS_STEP));
        state.physicsAccumulator -= PHYSICS_STEP;
        state.physicsSteps += 1;
        stepsThisFrame += 1;
      }
      state.sleepFrames = elapsed >= MIN_ROLL_DURATION && diceAreSleeping(dice)
        ? state.sleepFrames + 1
        : 0;
      if (impact > 1.5 && timestamp - state.lastImpactAt > 220) {
        state.lastImpactAt = timestamp;
        state.glow = Math.min(1, impact / 6);
        onImpact?.(impact);
      }
      if (state.sleepFrames >= SLEEP_FRAME_TARGET || elapsed >= MAX_ROLL_DURATION) {
        finishRoll(timestamp);
      }
      shouldDraw = true;
    }
    if (state.cupOpening) {
      state.cupLift = clamp((timestamp - state.cupOpenStartedAt) / 650, 0, 1);
      if (state.cupLift >= 1) {
        state.cupOpening = false;
        const resolve = state.resolveOpen;
        state.resolveOpen = null;
        resolve?.();
      }
      shouldDraw = true;
    }
    state.glow *= 0.9;

    // Static scenes are rendered only when state changes. The RAF callback is
    // intentionally kept alive so gestures can invalidate the canvas without
    // creating multiple animation loops.
    if (!shouldDraw) {
      state.frameId = canvas.requestAnimationFrame(render);
      return;
    }

    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    drawMesh(meshes.table, modelMatrix([0, -0.31, 0], [0, 0, 0, 1]), [0.014, 0.035, 0.075], 0);
    drawMesh(meshes.felt, modelMatrix([0, -0.055, 0], [0, 0, 0, 1]), [0.025, 0.19, 0.38], 2);
    drawMesh(meshes.tableRing, modelMatrix([0, 0.025, 0], [0, 0, 0, 1]), [0.025, 0.38, 0.72], 4, 0.18 + state.glow * 0.32);
    // The opaque cup must completely hide the dice while shaking and waiting.
    // Drawing them only after the cup has lifted also avoids impossible dice
    // silhouettes appearing above the cup rim on real devices.
    if (state.cupLift > 0.18) {
      dice.forEach((die) => {
        drawMesh(
          meshes.shadow,
          modelMatrix([die.position[0] + 0.08, 0.025, die.position[2] + 0.12], [0, 0, 0, 1], [1.18, 1, 0.72]),
          [0.004, 0.008, 0.018],
          0,
        );
      });
      dice.forEach((die) => {
        drawMesh(meshes.die, modelMatrix(die.position, die.quaternion), [1, 0.98, 0.9], 1, state.glow * 0.08);
      });
    }
    if (state.cupLift < 0.98) {
      const shake = state.rolling ? Math.sin(timestamp * 0.035) * 0.09 : 0;
      const lift = state.cupLift;
      const cupPosition = [lift * 2.9 + shake, 1.31 + lift * 3.7, -lift * 0.35];
      const tilt = lift * -0.42 + (state.rolling ? Math.sin(timestamp * 0.022) * 0.045 : 0);
      const cupQuaternion = [Math.sin(tilt / 2), 0, 0, Math.cos(tilt / 2)];
      drawMesh(meshes.cup, modelMatrix(cupPosition, cupQuaternion), [0.18, 0.018, 0.052], 3, state.glow * 0.12);
      const rimOffset = rotateVector(cupQuaternion, [0, -1.19, 0]);
      const bandOffset = rotateVector(cupQuaternion, [0, 1.1, 0]);
      drawMesh(
        meshes.cupRim,
        modelMatrix(cupPosition.map((value, index) => value + rimOffset[index]), cupQuaternion),
        [0.42, 0.06, 0.10],
        4,
        0.08 + state.glow * 0.18,
      );
      drawMesh(
        meshes.cupBand,
        modelMatrix(cupPosition.map((value, index) => value + bandOffset[index]), cupQuaternion),
        [0.30, 0.035, 0.075],
        4,
        0.04,
      );
    }
    gl.flush();
    state.dirty = false;
    state.frameId = canvas.requestAnimationFrame(render);
  };
  state.frameId = canvas.requestAnimationFrame(render);

  return {
    roll() {
      if (state.rolling) return Promise.reject(new Error("骰子正在滚动"));
      state.cupLift = 0;
      state.cupOpening = false;
      state.rolling = true;
      state.rollStartedAt = state.lastTime || 0;
      state.physicsAccumulator = 0;
      state.physicsSteps = 0;
      state.sleepFrames = 0;
      state.settleMs = 0;
      state.dirty = true;
      dice.forEach((die, index) => {
        const angle = (index / DICE_COUNT) * Math.PI * 2 + randomBetween(-0.4, 0.4);
        const radius = randomBetween(0.25, 0.75);
        die.position = [Math.cos(angle) * radius, randomBetween(0.9, 1.7), Math.sin(angle) * radius];
        die.velocity = [randomBetween(-2.8, 2.8), randomBetween(3.4, 5.6), randomBetween(-2.8, 2.8)];
        die.angularVelocity = [randomBetween(-11, 11), randomBetween(-11, 11), randomBetween(-11, 11)];
        die.quaternion = quatNormalize([
          randomBetween(-1, 1), randomBetween(-1, 1), randomBetween(-1, 1), randomBetween(-1, 1),
        ]);
      });
      return new Promise((resolve) => {
        state.resolveRoll = resolve;
      });
    },
    previewCupLift(progress) {
      if (!state.rolling && !state.cupOpening) {
        state.cupLift = clamp(progress, 0, 0.62);
        state.dirty = true;
      }
    },
    resetCupLift() {
      if (!state.cupOpening) {
        state.cupLift = 0;
        state.dirty = true;
      }
    },
    openCup() {
      state.cupOpening = true;
      state.cupOpenStartedAt = state.lastTime || Date.now();
      state.dirty = true;
      return new Promise((resolve) => {
        state.resolveOpen = resolve;
      });
    },
    getBoundsSnapshot() {
      const placement = getPlacementMetrics(dice);
      return {
        maxRadius: Math.max(...dice.map((die) => Math.hypot(die.position[0], die.position[2]))),
        safeRadius: CUP_SAFE_RADIUS,
        minSeparation: placement.minSeparation,
        maxTilt: placement.maxTilt,
        settleMs: state.settleMs,
        physicsSteps: state.physicsSteps,
      };
    },
    pause() {
      if (state.paused || state.disposed) return;
      state.paused = true;
      if (state.frameId != null) canvas.cancelAnimationFrame(state.frameId);
      state.frameId = null;
    },
    resume() {
      if (!state.paused || state.disposed) return;
      state.paused = false;
      state.lastTime = 0;
      state.physicsAccumulator = 0;
      state.dirty = true;
      state.frameId = canvas.requestAnimationFrame(render);
    },
    dispose() {
      state.disposed = true;
      if (state.frameId != null) canvas.cancelAnimationFrame(state.frameId);
      Object.values(meshes).forEach((mesh) => {
        Object.values(mesh.attributes).forEach((buffer) => gl.deleteBuffer(buffer));
        gl.deleteBuffer(mesh.indexBuffer);
      });
      gl.deleteProgram(program);
    },
  };
}
