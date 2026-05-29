import React, { useEffect, useState } from 'react';
import './Terms.css';
const TermsAndConditions = () => {
  const [terms, setTerms] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchTerms = async () => {
      try {
        const res = await fetch('http://localhost:5000/api/legal/terms');
        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.message || 'Failed to load terms');
        }
        setTerms(data.terms);
      } catch (e) {
        setError(e.message || 'Failed to load terms');
      } finally {
        setLoading(false);
      }
    };

    fetchTerms();
  }, []);

  if (loading) return <div style={{ padding: '24px' }}>Loading terms...</div>;
  if (error) return <div style={{ padding: '24px', color: 'red' }}>{error}</div>;
  if (!terms) return null;

  const sections = [
    terms.workspace_and_usage_policy,
    terms.data_upload_and_processing_policy,
    terms.payments_and_credits_policy,
    terms.transform_and_report_policy,
    terms.rescheduling_and_cancellation_policy,
    terms.privacy_and_security_policy,
    terms.general_terms,
  ].filter(Boolean);

  return (
  <div className="terms-page">
    <div className="terms-card">
      <div className="terms-header">
        <div className="terms-title-row">
          <h1 className="terms-title">Terms &amp; Conditions</h1>
          <span className="terms-version">
            Version {terms.version} · Effective{' '}
            {terms.effective_date &&
              new Date(terms.effective_date).toLocaleDateString()}
          </span>
        </div>
        <p className="terms-intro">{terms.introduction}</p>
      </div>

      {sections.map((section, idx) => (
        <section key={idx} className="terms-section">
          <h2 className="terms-section-title">{section.title}</h2>
          <ul className="terms-list">
            {section.points?.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </section>
      ))}

      {terms.footer_text && (
        <p className="terms-footer">{terms.footer_text}</p>
      )}
    </div>
  </div>
);
};

export default TermsAndConditions;