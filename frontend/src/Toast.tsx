type Props = {
  message: string
  onDismiss: () => void
}

/** A message that only informs: its one button dismisses it, and it never retries anything. */
function Toast({ message, onDismiss }: Props) {
  return (
    <div className="toast" role="alert">
      <p>{message}</p>
      <button
        type="button"
        className="toast-dismiss"
        aria-label="Dismiss"
        onClick={onDismiss}
      >
        ✕
      </button>
    </div>
  )
}

export default Toast
