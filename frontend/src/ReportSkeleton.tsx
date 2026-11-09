/**
 * Placeholder for a Cosmic Report while it loads: a Headline and three
 * Highlight Cards built from the same boxes as the real report (see
 * HighlightList), so nothing moves when the content arrives.
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
      <div className="highlights" aria-hidden="true">
        {[0, 1, 2].map((slot) => (
          <div key={slot} className="highlight-card">
            <div className="highlight-card-heading">
              <span className="skeleton-line skeleton-line-short" />
            </div>
            <div className="highlight-card-paragraph">
              <span className="skeleton-line" />
              <span className="skeleton-line" />
              <span className="skeleton-line skeleton-line-short" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ReportSkeleton
