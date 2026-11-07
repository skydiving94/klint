import React, { useState } from 'react';

// Antipattern: ignoring_composition (taking dozens of rigid layout/config props instead of `children` or slots)
interface RigidCardProps {
  titleText: string;
  subtitleText: string;
  headerIconUrl: string;
  showHeaderBorder: boolean;
  bodyParagraph1: string;
  bodyParagraph2: string;
  footerPrimaryButtonLabel: string;
  footerSecondaryButtonLabel: string;
  showFooterDisclaimer: boolean;
  disclaimerText: string;
  tooltipHoverText: string;
  setTooltipHoverText: (val: string) => void;
}

function DeeplyNestedLeafBadge({
  tooltipHoverText,
  setTooltipHoverText,
}: {
  tooltipHoverText: string;
  setTooltipHoverText: (val: string) => void;
}) {
  return (
    <span
      onMouseEnter={() =>
        setTooltipHoverText('Hovered badge!')
      }
    >
      {tooltipHoverText}
    </span>
  );
}

// Antipattern: prop_drilling (intermediate components forwarding props they never use)
function IntermediateCardSection({
  tooltipHoverText,
  setTooltipHoverText,
}: {
  tooltipHoverText: string;
  setTooltipHoverText: (val: string) => void;
}) {
  return (
    <div>
      <DeeplyNestedLeafBadge
        tooltipHoverText={tooltipHoverText}
        setTooltipHoverText={setTooltipHoverText}
      />
    </div>
  );
}

function RigidConfigurableCard(props: RigidCardProps) {
  return (
    <div className='card'>
      <header
        style={{
          borderBottom: props.showHeaderBorder
            ? '1px solid #ccc'
            : 'none',
        }}
      >
        <img
          src={props.headerIconUrl}
          alt=''
        />
        <h2>{props.titleText}</h2>
        <h4>{props.subtitleText}</h4>
      </header>
      <main>
        <p>{props.bodyParagraph1}</p>
        <p>{props.bodyParagraph2}</p>
        <IntermediateCardSection
          tooltipHoverText={props.tooltipHoverText}
          setTooltipHoverText={props.setTooltipHoverText}
        />
      </main>
      <footer>
        <button>{props.footerPrimaryButtonLabel}</button>
        <button>{props.footerSecondaryButtonLabel}</button>
        {props.showFooterDisclaimer && (
          <small>{props.disclaimerText}</small>
        )}
      </footer>
    </div>
  );
}

// Antipattern: god_component & improper_state_colocation
// Lifts `tooltipHoverText` to the top-level root when only `DeeplyNestedLeafBadge` uses it,
// and combines auth state, billing forms, theme management, and layout rendering in one component.
export function EnterpriseDashboardGodApp() {
  const [tooltipHoverText, setTooltipHoverText] = useState(
    'Default leaf tooltip',
  );
  const [authToken, setAuthToken] = useState(
    'hardcoded_front_token_abc123',
  );
  const [billingAddress, setBillingAddress] = useState('');
  const [invoiceHistory, setInvoiceHistory] = useState<
    string[]
  >([]);

  return (
    <div>
      <nav>Logged in with token: {authToken}</nav>
      <section>
        <input
          value={billingAddress}
          onChange={(e) =>
            setBillingAddress(e.target.value)
          }
        />
        <button
          onClick={() =>
            setInvoiceHistory([
              ...invoiceHistory,
              billingAddress,
            ])
          }
        >
          Save Billing
        </button>
      </section>
      <RigidConfigurableCard
        titleText='Account Overview'
        subtitleText=' Enterprise Tier'
        headerIconUrl='/icon.png'
        showHeaderBorder={true}
        bodyParagraph1='First paragraph configured via prop.'
        bodyParagraph2='Second paragraph configured via prop.'
        footerPrimaryButtonLabel='Upgrade'
        footerSecondaryButtonLabel='Cancel'
        showFooterDisclaimer={true}
        disclaimerText='Terms apply.'
        tooltipHoverText={tooltipHoverText}
        setTooltipHoverText={setTooltipHoverText}
      />
    </div>
  );
}
