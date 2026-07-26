import { RoundedBox } from "@react-three/drei";
import { RigidBody, RoundCuboidCollider } from "@react-three/rapier";
import { useCallback, useEffect, useRef } from "react";
import { Quaternion, Vector3 } from "three";

import { useDiceMaterialMaps } from "./materials";

const HALF_SIZE = 0.5;
const PIP_OFFSET = 0.225;
const PIP_LAYOUTS = {
  1: [[0, 0]],
  2: [[-PIP_OFFSET, PIP_OFFSET], [PIP_OFFSET, -PIP_OFFSET]],
  3: [[-PIP_OFFSET, PIP_OFFSET], [0, 0], [PIP_OFFSET, -PIP_OFFSET]],
  4: [
    [-PIP_OFFSET, PIP_OFFSET],
    [PIP_OFFSET, PIP_OFFSET],
    [-PIP_OFFSET, -PIP_OFFSET],
    [PIP_OFFSET, -PIP_OFFSET],
  ],
  5: [
    [-PIP_OFFSET, PIP_OFFSET],
    [PIP_OFFSET, PIP_OFFSET],
    [0, 0],
    [-PIP_OFFSET, -PIP_OFFSET],
    [PIP_OFFSET, -PIP_OFFSET],
  ],
  6: [
    [-PIP_OFFSET, PIP_OFFSET],
    [-PIP_OFFSET, 0],
    [-PIP_OFFSET, -PIP_OFFSET],
    [PIP_OFFSET, PIP_OFFSET],
    [PIP_OFFSET, 0],
    [PIP_OFFSET, -PIP_OFFSET],
  ],
};

const FACE_DEFINITIONS = [
  { value: 1, axis: "y", side: 1, normal: [0, 1, 0] },
  { value: 6, axis: "y", side: -1, normal: [0, -1, 0] },
  { value: 2, axis: "z", side: 1, normal: [0, 0, 1] },
  { value: 5, axis: "z", side: -1, normal: [0, 0, -1] },
  { value: 3, axis: "x", side: 1, normal: [1, 0, 0] },
  { value: 4, axis: "x", side: -1, normal: [-1, 0, 0] },
];

/**
 * Converts a 2D pip coordinate into the local position of a cube face.
 */
function getPipTransform(face, horizontal, vertical) {
  const surface = (HALF_SIZE + 0.008) * face.side;
  if (face.axis === "y") {
    return {
      position: [horizontal, surface, face.side * vertical],
      rotation: [0, 0, 0],
    };
  }
  if (face.axis === "z") {
    return {
      position: [horizontal, vertical, surface],
      rotation: [Math.PI / 2, 0, 0],
    };
  }
  return {
    position: [surface, vertical, face.side * horizontal],
    rotation: [0, 0, Math.PI / 2],
  };
}

/**
 * Renders one slightly inset, glossy pip on a die face.
 */
function Pip({ face, horizontal, vertical }) {
  const transform = getPipTransform(face, horizontal, vertical);
  const color = face.value === 1 || face.value === 4 ? "#e7333f" : "#174cba";

  return (
    <mesh
      position={transform.position}
      rotation={transform.rotation}
      castShadow
      receiveShadow
    >
      <cylinderGeometry args={[0.082, 0.082, 0.025, 24]} />
      <meshPhysicalMaterial
        color={color}
        roughness={0.27}
        metalness={0.02}
        clearcoat={0.65}
        clearcoatRoughness={0.2}
      />
    </mesh>
  );
}

/**
 * Reads the physically settled top face from a Rapier rotation.
 */
export function getTopFaceValue(rotation) {
  const quaternion = new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w);
  const up = new Vector3(0, 1, 0);
  let topValue = 1;
  let bestAlignment = -Infinity;

  FACE_DEFINITIONS.forEach((face) => {
    const direction = new Vector3(...face.normal).applyQuaternion(quaternion);
    const alignment = direction.dot(up);
    if (alignment > bestAlignment) {
      bestAlignment = alignment;
      topValue = face.value;
    }
  });
  return topValue;
}

/**
 * Renders one rounded, physical six-sided die with colored pips.
 */
export default function Dice({
  diceId,
  launch,
  visible,
  onBodyReady,
  onSettled,
  onHit,
}) {
  const bodyRef = useRef(null);
  const reportedRef = useRef(false);
  const materialMaps = useDiceMaterialMaps();

  useEffect(() => {
    if (bodyRef.current) {
      onBodyReady(diceId, bodyRef.current);
    }
    return () => onBodyReady(diceId, null);
  }, [diceId, onBodyReady]);

  const handleSleep = useCallback(() => {
    if (!reportedRef.current && bodyRef.current) {
      reportedRef.current = true;
      onSettled(diceId, getTopFaceValue(bodyRef.current.rotation()));
    }
  }, [diceId, onSettled]);

  const handleContactForce = useCallback(
    (event) => {
      if (visible && event.totalForceMagnitude > 14) {
        const position = bodyRef.current?.translation();
        onHit({
          force: event.totalForceMagnitude,
          position: position ? [position.x, position.y, position.z] : [0, 0, 0],
        });
      }
    },
    [onHit, visible],
  );

  return (
    <RigidBody
      ref={bodyRef}
      colliders={false}
      position={launch.position}
      rotation={launch.rotation}
      linearVelocity={launch.linearVelocity}
      angularVelocity={launch.angularVelocity}
      linearDamping={0.42}
      angularDamping={0.48}
      ccd
      canSleep
      onSleep={handleSleep}
      onContactForce={handleContactForce}
    >
      <group visible={visible}>
        <RoundedBox
          args={[1, 1, 1]}
          radius={0.13}
          smoothness={4}
          castShadow
          receiveShadow
        >
          <meshPhysicalMaterial
            color="#fbfbf7"
            roughness={0.3}
            roughnessMap={materialMaps.roughnessMap}
            bumpMap={materialMaps.bumpMap}
            bumpScale={0.014}
            metalness={0.01}
            clearcoat={0.82}
            clearcoatRoughness={0.2}
            sheen={0.16}
            sheenColor="#d9e8ff"
            envMapIntensity={1.28}
          />
        </RoundedBox>
        {FACE_DEFINITIONS.flatMap((face) =>
          PIP_LAYOUTS[face.value].map(([horizontal, vertical], index) => (
            <Pip
              key={`${face.value}-${index}`}
              face={face}
              horizontal={horizontal}
              vertical={vertical}
            />
          )),
        )}
      </group>
      <RoundCuboidCollider
        args={[0.47, 0.47, 0.47, 0.11]}
        density={1.25}
        friction={0.72}
        restitution={0.42}
      />
    </RigidBody>
  );
}
