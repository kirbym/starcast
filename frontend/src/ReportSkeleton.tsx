/**
 * Placeholder for a Cosmic Report while it loads: a Headline and three
 * Highlight Cards built from the same boxes as the real report, so nothing
 * moves when the content arrives.
 */
function ReportSkeleton() {
  return (
    <div
      className="report"
      role="status"
      aria-busy="true"
      aria-label="Loading tonight's report"
    >
      <div className="headline" aria-hidden="true">
        <span className="skeleton-line" />
        <span className="skeleton-line" />
        <span className="skeleton-line skeleton-line-short" />
      </div>
      <ul className="highlight-list" aria-hidden="true">
        {[0, 1, 2].map((slot) => (
          <li key={slot} className="highlight-card">
            <div className="mini-headline">
              <span className="skeleton-line skeleton-line-short" />
            </div>
            <div className="highlight-paragraph">
              <span className="skeleton-line" />
              <span className="skeleton-line" />
              <span className="skeleton-line skeleton-line-short" />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default ReportSkeleton
