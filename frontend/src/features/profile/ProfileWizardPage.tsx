import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { ApiError } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import { type ProfilePayload, saveProfile } from "./profile-api";

type ProfileFormErrors = Partial<Record<keyof ProfilePayload | "form", string>>;

const baseCurrencies = ["USD", "EUR", "ILS", "GBP"];
const timeHorizons = ["1-3 years", "3-7 years", "7-10 years", "10+ years"];
const investmentFrequencies = ["weekly", "monthly", "quarterly", "annually"];

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
  });
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = { ...form, display_name: form.display_name.trim() };
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

        <div className="form-actions">
          <Button
            disabled={saveMutation.isPending}
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
