import {
  CuboidCollider,
  Physics,
  RigidBody,
} from "@react-three/rapier";
import { useCallback, useEffect, useMemo, useRef } from "react";

import Dice, { getTopFaceValue } from "./Dice";
import { createPhysicalLaunches, DICE_PER_PLAYER } from "./gameLogic";

const WALL_SEGMENTS = Array.from({ length: 12 }, (_, index) => {
  const angle = (index / 12) * Math.PI * 2;
  const radius = 3.18;
  return {
    position: [Math.sin(angle) * radius, 3.8, Math.cos(angle) * radius],
    rotation: [0, angle, 0],
  };
});

/**
 * Runs one independent five-dice Rapier simulation for a player.
 */
export default function PhysicsWorld({
  playerId,
  roundId,
  visible,
  onSettled,
  onHit,
}) {
  const launches = useMemo(
    () => createPhysicalLaunches(playerId, roundId),
    [playerId, roundId],
  );
  const bodiesRef = useRef(new Map());
  const valuesRef = useRef(new Map());
  const didReportRef = useRef(false);

  const reportIfReady = useCallback(() => {
    if (didReportRef.current || valuesRef.current.size !== DICE_PER_PLAYER) {
      return;
    }
    didReportRef.current = true;
    const values = Array.from(
      { length: DICE_PER_PLAYER },
      (_, index) => valuesRef.current.get(index),
    );
    onSettled(playerId, values);
  }, [onSettled, playerId]);

  const handleBodyReady = useCallback((diceId, body) => {
    if (body) {
      bodiesRef.current.set(diceId, body);
    } else {
      bodiesRef.current.delete(diceId);
    }
  }, []);

  const handleDieSettled = useCallback(
    (diceId, value) => {
      valuesRef.current.set(diceId, value);
      reportIfReady();
    },
    [reportIfReady],
  );

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      bodiesRef.current.forEach((body, diceId) => {
        if (!valuesRef.current.has(diceId)) {
          body.setLinvel({ x: 0, y: 0, z: 0 }, false);
          body.setAngvel({ x: 0, y: 0, z: 0 }, false);
          valuesRef.current.set(diceId, getTopFaceValue(body.rotation()));
        }
      });
      reportIfReady();
    }, 4200);
    return () => window.clearTimeout(timeoutId);
  }, [reportIfReady]);

  return (
    <Physics gravity={[0, -18, 0]} timeStep={1 / 60} colliders={false}>
      <RigidBody type="fixed" colliders={false}>
        <CuboidCollider
          args={[4.55, 0.15, 4.55]}
          position={[0, -0.18, 0]}
          friction={0.86}
          restitution={0.3}
        />
        {WALL_SEGMENTS.map((wall, index) => (
          <CuboidCollider
            key={index}
            args={[0.94, 4, 0.12]}
            position={wall.position}
            rotation={wall.rotation}
            friction={0.75}
            restitution={0.34}
          />
        ))}
      </RigidBody>
      {launches.map((launch, index) => (
        <Dice
          key={`${playerId}-${roundId}-${index}`}
          diceId={index}
          launch={launch}
          visible={visible}
          onBodyReady={handleBodyReady}
          onSettled={handleDieSettled}
          onHit={onHit}
        />
      ))}
    </Physics>
  );
}
