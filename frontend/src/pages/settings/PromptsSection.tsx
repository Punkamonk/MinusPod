import CollapsibleSection from '../../components/CollapsibleSection';
import PromptField from './PromptField';

const OVERRIDE_HELP =
  'Optional. Added to this pass at run time; leave blank to use the default prompt '
  + 'unchanged. Put {override} in a customized prompt above to control where it goes.';

interface PromptsSectionProps {
  systemPrompt: string;
  verificationPrompt: string;
  systemPromptOverride: string;
  verificationPromptOverride: string;
  onSystemPromptChange: (prompt: string) => void;
  onVerificationPromptChange: (prompt: string) => void;
  onSystemPromptOverrideChange: (prompt: string) => void;
  onVerificationPromptOverrideChange: (prompt: string) => void;
  onResetPrompts: () => void;
  resetIsPending: boolean;
}

function PromptsSection({
  systemPrompt,
  verificationPrompt,
  systemPromptOverride,
  verificationPromptOverride,
  onSystemPromptChange,
  onVerificationPromptChange,
  onSystemPromptOverrideChange,
  onVerificationPromptOverrideChange,
  onResetPrompts,
  resetIsPending,
}: PromptsSectionProps) {
  return (
    <CollapsibleSection title="Prompts">
      <div className="space-y-6">
        <PromptField
          id="systemPrompt"
          label="First Pass System Prompt"
          value={systemPrompt}
          onChange={onSystemPromptChange}
          helpText="Instructions sent to the AI model for the initial ad detection pass"
        />
        <PromptField
          id="systemPromptOverride"
          label="First Pass Override"
          value={systemPromptOverride}
          onChange={onSystemPromptOverrideChange}
          rows={3}
          helpText={OVERRIDE_HELP}
        />

        <PromptField
          id="verificationPrompt"
          label="Verification Prompt"
          value={verificationPrompt}
          onChange={onVerificationPromptChange}
          helpText="Instructions for the verification pass to detect ads missed by the first pass"
        />
        <PromptField
          id="verificationPromptOverride"
          label="Verification Override"
          value={verificationPromptOverride}
          onChange={onVerificationPromptOverrideChange}
          rows={3}
          helpText={OVERRIDE_HELP}
        />

        <button
          onClick={onResetPrompts}
          disabled={resetIsPending}
          className="px-4 py-2 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 disabled:opacity-50 transition-colors"
        >
          {resetIsPending ? 'Resetting...' : 'Reset Prompts to Default'}
        </button>
      </div>
    </CollapsibleSection>
  );
}

export default PromptsSection;
