import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./ui.jsx";

const CAMERA_ERRORS = {
  NotAllowedError: "Camera access was blocked. Allow it in your browser's site settings, then try again.",
  NotFoundError: "No webcam was found on this computer.",
  NotReadableError: "Your webcam is being used by another app. Close it and try again.",
};

/** Modal webcam capture for laptops and desktop cameras. */
export default function Webcam({ onCapture, onClose }) {
  const video = useRef();
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [flash, setFlash] = useState(false);

  function capture() {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d").drawImage(v, 0, 0);
    setFlash(true);
    canvas.toBlob((blob) => onCapture(new File([blob], "webcam.jpg", { type: "image/jpeg" })), "image/jpeg", 0.92);
  }

  useEffect(() => {
    let stream;
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser can't access a webcam.");
    } else {
      navigator.mediaDevices
        .getUserMedia({ video: { width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
        .then((s) => {
          if (cancelled) return s.getTracks().forEach((t) => t.stop());
          stream = s;
          video.current.srcObject = s;
        })
        .catch((e) => setError(CAMERA_ERRORS[e.name] || "Couldn't start the webcam."));
    }
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        capture();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      cancelled = true;
      window.removeEventListener("keydown", onKey);
      stream?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal webcam-modal" role="dialog" aria-modal="true" aria-label="Take a photo with your webcam">
        <header className="modal-head">
          <div>
            <h2 className="display">Webcam snap</h2>
            <small className="muted">Hold your plate up to the camera, or point the camera down at your table.</small>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close webcam" title="Close (Esc)"><Icon name="x" size={16} /></button>
        </header>
        <div className="webcam-view">
          {error ? (
            <div className="webcam-error"><span aria-hidden="true">📷</span><p>{error}</p></div>
          ) : (
            <>
              <video ref={video} autoPlay playsInline muted onLoadedData={() => setReady(true)} />
              {!ready && <div className="webcam-loading"><span className="spinner" /> Starting camera…</div>}
              <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
              {flash && <div className="flash" onAnimationEnd={() => setFlash(false)} />}
            </>
          )}
        </div>
        <footer className="modal-foot">
          <span className="muted small key-hint keep-space"><kbd>Space</kbd> capture · <kbd>Esc</kbd> close</span>
          <button className="shutter" onClick={capture} disabled={!ready || !!error} aria-label="Capture photo" title="Capture (Space)">
            <span />
          </button>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
