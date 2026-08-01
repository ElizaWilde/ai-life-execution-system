"use client";

import { PointerEvent, useEffect, useRef, useState } from "react";

type CharacterFrame = 0 | 1 | 2 | 3;

export default function CoachCharacter2D() {
  const [frame, setFrame] = useState<CharacterFrame>(0);
  const [speech, setSpeech] = useState("Need help?");
  const gazeFrame = useRef<CharacterFrame>(0);

  useEffect(() => {
    let blinkTimer = 0;
    let restoreTimer = 0;
    function scheduleBlink() {
      blinkTimer = window.setTimeout(() => {
        setFrame(1);
        restoreTimer = window.setTimeout(() => {
          setFrame(gazeFrame.current);
          scheduleBlink();
        }, 150);
      }, 2600 + Math.random() * 2600);
    }
    scheduleBlink();
    return () => {
      window.clearTimeout(blinkTimer);
      window.clearTimeout(restoreTimer);
    };
  }, []);

  function trackGaze(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const horizontal = (event.clientX - bounds.left) / bounds.width;
    const nextFrame: CharacterFrame = horizontal < 0.38 ? 2 : horizontal > 0.62 ? 3 : 0;
    gazeFrame.current = nextFrame;
    setFrame(nextFrame);
    setSpeech(nextFrame === 2 ? "Over here?" : nextFrame === 3 ? "Ready!" : "Need help?");
  }

  function resetGaze() {
    gazeFrame.current = 0;
    setFrame(0);
    setSpeech("Need help?");
  }

  return <div className="coach-character-2d" onPointerLeave={resetGaze} onPointerMove={trackGaze}>
    <span className="coach-character-speech">{speech}</span>
    <span
      aria-label="Animated AI Coach character"
      className="coach-character-sprite"
      role="img"
      style={{ backgroundPosition: `${frame * 33.333333}% center` }}
    />
  </div>;
}
