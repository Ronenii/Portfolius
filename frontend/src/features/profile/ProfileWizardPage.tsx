import { useMutation, useQueryClient } from "@tanstack/react-query";
import { HelpCircle, Save, X } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { ApiError } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import { type ProfilePayload, saveProfile } from "./profile-api";

type ProfileFormErrors = Partial<Record<keyof ProfilePayload | "form", string>>;

const baseCurrencies = ["USD", "EUR", "ILS", "GBP"];
const timeHorizons = ["1-3 years", "3-7 years", "7-10 years", "10+ years"];
const investmentFrequencies = ["weekly", "monthly", "quarterly", "annually"];
const riskTolerances = [
  { label: "Conservative", value: "conservative" },
  { label: "Balanced", value: "balanced" },
  { label: "Aggressive", value: "aggressive" },
];
const maxKeywordLength = 40;
const maxKeywords = 30;

function validateProfile(payload: ProfilePayload): ProfileFormErrors {
  const errors: ProfileFormErrors = {};

  if (!payload.display_name.trim()) {
    errors.display_name = "Display name is required";
  }
  if (!payload.base_currency) {
    errors.base_currency = "Base currency is required";
  }
  if (!payload.time_horizon) {
    errors.time_horizon = "Time horizon is required";
  }
  if (!payload.investment_frequency) {
    errors.investment_frequency = "Investment frequency is required";
  }

  if (payload.goal_target_amount !== null) {
    const numericValue = Number(payload.goal_target_amount);
    if (!Number.isFinite(numericValue) || numericValue < 0) {
      errors.goal_target_amount = "Must be zero or greater";
    }
  }

  if (payload.contribution_amount !== null) {
    const numericValue = Number(payload.contribution_amount);
    if (!Number.isFinite(numericValue) || numericValue < 0) {
      errors.contribution_amount = "Must be zero or greater";
    }
  }

  return errors;
}

export default function ProfileWizardPage() {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ProfilePayload>({
    display_name: "",
    base_currency: "",
    time_horizon: "",
    investment_frequency: "",
    risk_tolerance: null,
    interest_tags: [],
    excluded_sectors: [],
    goals_note: null,
    goal_target_amount: "",
    contribution_amount: "",
  });
  const [interestInput, setInterestInput] = useState("");
  const [avoidInput, setAvoidInput] = useState("");
  const [errors, setErrors] = useState<ProfileFormErrors>({});

  const saveMutation = useMutation({
    mutationFn: (payload: ProfilePayload) => saveProfile(accessToken ?? "", payload),
    onSuccess: (profile) => {
      queryClient.setQueryData(["profile", accessToken], profile);
      navigate("/dashboard", { replace: true });
    },
    onError: (error) => {
      setErrors({
        form:
          error instanceof ApiError
            ? error.message
            : "Profile could not be saved. Try again.",
      });
    },
  });

  function updateField<Key extends keyof ProfilePayload>(
    field: Key,
    value: ProfilePayload[Key]
  ) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined, form: undefined }));
  }

  function addKeyword(
    field: "interest_tags" | "excluded_sectors",
    value: string,
    clearInput: () => void
  ) {
    const keyword = value.trim().slice(0, maxKeywordLength).toLowerCase();
    if (!keyword) {
      clearInput();
      return;
    }

    setForm((current) => {
      const currentValues = current[field];
      const alreadyExists = currentValues.some(
        (currentValue) => currentValue.toLowerCase() === keyword.toLowerCase()
      );
      const canAdd = !alreadyExists && currentValues.length < maxKeywords;
      const nextValues = canAdd
        ? [...currentValues, keyword]
        : currentValues;
      return { ...current, [field]: nextValues };
    });
    clearInput();
    setErrors((current) => ({ ...current, [field]: undefined, form: undefined }));
  }

  function removeKeyword(
    field: "interest_tags" | "excluded_sectors",
    value: string
  ) {
    setForm((current) => ({
      ...current,
      [field]: current[field].filter((currentValue) => currentValue !== value),
    }));
  }

  function handleKeywordKeyDown(
    event: KeyboardEvent<HTMLInputElement>,
    field: "interest_tags" | "excluded_sectors",
    values: string[],
    clearInput: () => void
  ) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addKeyword(field, event.currentTarget.value, clearInput);
      return;
    }

    if (event.key === "Backspace" && !event.currentTarget.value && values.length > 0) {
      event.preventDefault();
      removeKeyword(field, values[values.length - 1]);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const goalsNote = form.goals_note?.trim() || null;
    const payload = {
      ...form,
      display_name: form.display_name.trim(),
      goals_note: goalsNote,
      goal_target_amount: form.goal_target_amount?.trim() || null,
      contribution_amount: form.contribution_amount?.trim() || null,
    };
    const validationErrors = validateProfile(payload);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    saveMutation.mutate(payload);
  }

  return (
    <section className="page-section profile-setup" aria-labelledby="profile-setup-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">First run</p>
          <h1 id="profile-setup-title">Profile setup</h1>
        </div>
      </header>

      <form className="profile-form" noValidate onSubmit={handleSubmit}>
        {errors.form ? <p className="form-error">{errors.form}</p> : null}

        <div className="form-grid">
          <div className="field">
            <label htmlFor="display-name">Display name</label>
            <input
              id="display-name"
              name="display_name"
              type="text"
              value={form.display_name}
              onChange={(event) => updateField("display_name", event.target.value)}
            />
            {errors.display_name ? (
              <span className="field-error">{errors.display_name}</span>
            ) : null}
          </div>

          <div className="field">
            <label htmlFor="base-currency">Base currency</label>
            <select
              id="base-currency"
              name="base_currency"
              value={form.base_currency}
              onChange={(event) => updateField("base_currency", event.target.value)}
            >
              <option value="">Select currency</option>
              {baseCurrencies.map((currency) => (
                <option key={currency} value={currency}>
                  {currency}
                </option>
              ))}
            </select>
            {errors.base_currency ? (
              <span className="field-error">{errors.base_currency}</span>
            ) : null}
          </div>

          <div className="field">
            <label htmlFor="time-horizon">Time horizon</label>
            <select
              id="time-horizon"
              name="time_horizon"
              value={form.time_horizon}
              onChange={(event) => updateField("time_horizon", event.target.value)}
            >
              <option value="">Select horizon</option>
              {timeHorizons.map((horizon) => (
                <option key={horizon} value={horizon}>
                  {horizon}
                </option>
              ))}
            </select>
            {errors.time_horizon ? (
              <span className="field-error">{errors.time_horizon}</span>
            ) : null}
          </div>

          <div className="field">
            <label htmlFor="investment-frequency">Investment frequency</label>
            <select
              id="investment-frequency"
              name="investment_frequency"
              value={form.investment_frequency}
              onChange={(event) =>
                updateField("investment_frequency", event.target.value)
              }
            >
              <option value="">Select frequency</option>
              {investmentFrequencies.map((frequency) => (
                <option key={frequency} value={frequency}>
                  {frequency}
                </option>
              ))}
            </select>
            {errors.investment_frequency ? (
              <span className="field-error">{errors.investment_frequency}</span>
            ) : null}
          </div>
        </div>

        <div className="profile-form-panes">
          <section className="profile-form-section" aria-labelledby="profile-goals-title">
            <div className="profile-form-section-heading">
              <p className="eyebrow">Assistant context</p>
              <h2 id="profile-goals-title">Interests & goals</h2>
            </div>

            <fieldset className="choice-group">
              <legend>Risk tolerance</legend>
              <div className="choice-row">
                {riskTolerances.map((option) => (
                  <label className="choice-option" key={option.value}>
                    <input
                      checked={form.risk_tolerance === option.value}
                      name="risk_tolerance"
                      type="radio"
                      value={option.value}
                      onChange={() => updateField("risk_tolerance", option.value)}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <fieldset className="choice-group">
              <legend>Interests</legend>
              <div className="keyword-label-row">
                <label htmlFor="interest-keyword">Add interest keyword</label>
                <span className="tooltip-shell">
                  <button
                    aria-label="Interest keyword examples"
                    className="tooltip-trigger"
                    type="button"
                  >
                    <HelpCircle aria-hidden="true" />
                  </button>
                  <span className="tooltip-content" role="tooltip">
                    Examples: dividends, AI infrastructure, low-fee ETFs, emerging
                    markets.
                  </span>
                </span>
              </div>
              <div className="keyword-entry">
                {form.interest_tags.map((keyword) => (
                  <span className="keyword-chip" key={keyword}>
                    {keyword}
                    <button
                      aria-label={`Remove ${keyword}`}
                      type="button"
                      onClick={() => removeKeyword("interest_tags", keyword)}
                    >
                      <X aria-hidden="true" />
                    </button>
                  </span>
                ))}
                <input
                  id="interest-keyword"
                  maxLength={maxKeywordLength}
                  placeholder="Type and press Enter"
                  type="text"
                  value={interestInput}
                  onBlur={(event) =>
                    addKeyword("interest_tags", event.currentTarget.value, () =>
                      setInterestInput("")
                    )
                  }
                  onChange={(event) => setInterestInput(event.target.value)}
                  onKeyDown={(event) =>
                    handleKeywordKeyDown(
                      event,
                      "interest_tags",
                      form.interest_tags,
                      () => setInterestInput("")
                    )
                  }
                />
              </div>
            </fieldset>

            <fieldset className="choice-group">
              <legend>Preferences to avoid</legend>
              <div className="keyword-label-row">
                <label htmlFor="avoid-keyword">Add avoid keyword</label>
                <span className="tooltip-shell">
                  <button
                    aria-label="Avoid keyword examples"
                    className="tooltip-trigger"
                    type="button"
                  >
                    <HelpCircle aria-hidden="true" />
                  </button>
                  <span className="tooltip-content" role="tooltip">
                    Examples: tobacco, high fee funds, speculative crypto, weapons.
                  </span>
                </span>
              </div>
              <div className="keyword-entry">
                {form.excluded_sectors.map((keyword) => (
                  <span className="keyword-chip" key={keyword}>
                    {keyword}
                    <button
                      aria-label={`Remove ${keyword}`}
                      type="button"
                      onClick={() => removeKeyword("excluded_sectors", keyword)}
                    >
                      <X aria-hidden="true" />
                    </button>
                  </span>
                ))}
                <input
                  id="avoid-keyword"
                  maxLength={maxKeywordLength}
                  placeholder="Type and press Enter"
                  type="text"
                  value={avoidInput}
                  onBlur={(event) =>
                    addKeyword("excluded_sectors", event.currentTarget.value, () =>
                      setAvoidInput("")
                    )
                  }
                  onChange={(event) => setAvoidInput(event.target.value)}
                  onKeyDown={(event) =>
                    handleKeywordKeyDown(
                      event,
                      "excluded_sectors",
                      form.excluded_sectors,
                      () => setAvoidInput("")
                    )
                  }
                />
              </div>
            </fieldset>

            <div className="field">
              <label htmlFor="goals-note">Goals note</label>
              <textarea
                id="goals-note"
                maxLength={1000}
                name="goals_note"
                rows={4}
                value={form.goals_note ?? ""}
                onChange={(event) => updateField("goals_note", event.target.value)}
              />
              <span className="field-hint">
                This helps the assistant understand your portfolio goals.
              </span>
            </div>
          </section>

          <section
            className="profile-form-section"
            aria-labelledby="profile-projection-title"
          >
            <div className="profile-form-section-heading">
              <p className="eyebrow">Assistant context</p>
              <h2 id="profile-projection-title">Goal projection</h2>
            </div>

            <div className="form-grid">
              <div className="field">
                <label htmlFor="goal-target-amount">Goal target amount</label>
                <input
                  id="goal-target-amount"
                  inputMode="decimal"
                  value={form.goal_target_amount ?? ""}
                  onChange={(event) =>
                    updateField("goal_target_amount", event.target.value)
                  }
                />
                {errors.goal_target_amount ? (
                  <span className="field-error">{errors.goal_target_amount}</span>
                ) : null}
              </div>

              <div className="field">
                <label htmlFor="contribution-amount">Contribution amount</label>
                <input
                  id="contribution-amount"
                  inputMode="decimal"
                  value={form.contribution_amount ?? ""}
                  onChange={(event) =>
                    updateField("contribution_amount", event.target.value)
                  }
                />
                {errors.contribution_amount ? (
                  <span className="field-error">{errors.contribution_amount}</span>
                ) : null}
              </div>
            </div>
          </section>
        </div>

        <div className="form-actions">
          <Button
            loading={saveMutation.isPending}
            icon={Save}
            type="submit"
            variant="primary"
          >
            {saveMutation.isPending ? "Saving profile" : "Save profile"}
          </Button>
        </div>
      </form>
    </section>
  );
}
