"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, PointerEvent as ReactPointerEvent } from "react";

type Position = { x: number; y: number };

const COACH_POSITION_KEY = "ai-life-coach-position";

const directionFrames: Record<number, number> = {
  0: 6,
  1: 7,
  2: 0,
  3: 1,
  4: 2,
  [-4]: 2,
  [-3]: 3,
  [-2]: 4,
  [-1]: 5,
};

function frameForVector(x: number, y: number) {
  const sector = Math.round(Math.atan2(y, x) / (Math.PI / 4));
  return directionFrames[sector] ?? 0;
}

function boundedPosition(position: Position): Position {
  const width = 154;
  const height = 220;
  return {
    x: Math.max(12, Math.min(position.x, window.innerWidth - width - 12)),
    y: Math.max(64, Math.min(position.y, window.innerHeight - height - 12)),
  };
}

export default function CoachCharacter2D() {
  const coachRef = useRef<HTMLAnchorElement>(null);
  const drag = useRef({
    active: false,
    moved: false,
    offsetX: 0,
    offsetY: 0,
    pointerId: -1,
    startX: 0,
    startY: 0,
  });
  const positionRef = useRef<Position>({ x: 24, y: 220 });
  const [frame, setFrame] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState<Position>({ x: 24, y: 220 });

  useEffect(() => {
    let initial = boundedPosition({ x: window.innerWidth - 188, y: window.innerHeight - 248 });
    try {
      const saved = window.localStorage.getItem(COACH_POSITION_KEY);
      if (saved) initial = boundedPosition(JSON.parse(saved) as Position);
    } catch {
      window.localStorage.removeItem(COACH_POSITION_KEY);
    }
    positionRef.current = initial;
    setPosition(initial);

    function followPointer(event: PointerEvent) {
      const coach = coachRef.current;
      if (!coach) return;
      const bounds = coach.getBoundingClientRect();
      setFrame(frameForVector(
        event.clientX - (bounds.left + bounds.width / 2),
        event.clientY - (bounds.top + bounds.height * 0.45),
      ));
    }

    function keepOnScreen() {
      const next = boundedPosition(positionRef.current);
      positionRef.current = next;
      setPosition(next);
    }

    window.addEventListener("pointermove", followPointer, { passive: true });
    window.addEventListener("resize", keepOnScreen);
    return () => {
      window.removeEventListener("pointermove", followPointer);
      window.removeEventListener("resize", keepOnScreen);
    };
  }, []);

  function startCoachConversation() {
    window.sessionStorage.removeItem("ai-life-coach-conversation");
    window.dispatchEvent(new Event("ai-life:start-coach-conversation"));
  }

  function beginDrag(event: ReactPointerEvent<HTMLAnchorElement>) {
    if (event.button !== 0) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    drag.current = {
      active: true,
      moved: false,
      offsetX: event.clientX - bounds.left,
      offsetY: event.clientY - bounds.top,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsDragging(true);
  }

  function continueDrag(event: ReactPointerEvent<HTMLAnchorElement>) {
    if (!drag.current.active || drag.current.pointerId !== event.pointerId) return;
    if (Math.hypot(event.clientX - drag.current.startX, event.clientY - drag.current.startY) > 4) {
      drag.current.moved = true;
    }
    const next = boundedPosition({
      x: event.clientX - drag.current.offsetX,
      y: event.clientY - drag.current.offsetY,
    });
    positionRef.current = next;
    setPosition(next);
  }

  function endDrag(event: ReactPointerEvent<HTMLAnchorElement>) {
    if (!drag.current.active || drag.current.pointerId !== event.pointerId) return;
    drag.current.active = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setIsDragging(false);
    window.localStorage.setItem(COACH_POSITION_KEY, JSON.stringify(positionRef.current));
  }

  function handleClick(event: ReactMouseEvent<HTMLAnchorElement>) {
    if (drag.current.moved) {
      event.preventDefault();
      drag.current.moved = false;
      return;
    }
    startCoachConversation();
  }

  return (
    <Link
      aria-label="Start a new AI Coach conversation"
      className={`floating-coach ${isDragging ? "dragging" : ""}`}
      draggable={false}
      href="/coach"
      onClick={handleClick}
      onPointerCancel={endDrag}
      onPointerDown={beginDrag}
      onPointerMove={continueDrag}
      onPointerUp={endDrag}
      ref={coachRef}
      style={{ left: position.x, top: position.y }}
    >
      <span className="floating-coach-speech">Drag me or click to talk</span>
      <span
        aria-hidden="true"
        className="floating-coach-sprite"
        style={{ backgroundPosition: `${frame * 14.285714}% center` }}
      />
    </Link>
  );
}
