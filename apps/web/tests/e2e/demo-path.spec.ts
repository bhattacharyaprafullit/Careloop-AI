import { expect, test } from "@playwright/test";

const ALL_STATES = [
  "RESULT_ISSUED",
  "PATIENT_NOTIFIED",
  "ACKNOWLEDGED",
  "CONFIRMATORY_PENDING",
  "REFERRAL_SENT",
  "REJECTED",
  "REFERRAL_ACCEPTED",
  "APPOINTMENT_BOOKED",
  "SEEN",
  "TREATMENT_OR_SURVEILLANCE",
  "CLOSED",
];

test("e2e_case_page_shows_all_states", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(page.getByText("Demo only, synthetic data")).toBeVisible();

  await page.getByTestId("launch-demo-btn").click();
  await expect(page).toHaveURL(/\/app\/queue/);

  const firstOpenBtn = page.locator('[data-testid^="open-case-"]').first();
  await expect(firstOpenBtn).toBeVisible();
  await firstOpenBtn.click();

  await expect(page.getByTestId("lifecycle-stepper")).toBeVisible();
  for (const state of ALL_STATES) {
    await expect(page.getByTestId(`stepper-state-${state}`)).toContainText(
      state
    );
  }
});

test("demo-path end-to-end closed loop journey across 1280px and 375px", async ({
  page,
}) => {
  // 1. Desktop 1280px: Launch live demo from landing page
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await expect(page.getByText("Demo only, synthetic data")).toBeVisible();
  await page.getByTestId("launch-demo-btn").click();
  await expect(page).toHaveURL(/\/app\/queue/);

  // 2. Verify queue tabs (All, Overdue, Unassigned, Rejected, Needs approval)
  await page.getByTestId("tab-overdue").click();
  await page.getByTestId("tab-unassigned").click();
  await page.getByTestId("tab-rejected").click();
  await page.getByTestId("tab-needs_approval").click();
  await page.getByTestId("tab-all").click();

  // 3. Ingest a fresh abnormal screening result (starts at RESULT_ISSUED)
  await page.getByTestId("toggle-ingest-btn").click();
  await page.getByTestId("ingest-screening-form").locator('button[type="submit"]').click();

  // Open a case in RESULT_ISSUED or open the first case in the queue
  const resultIssuedRow = page
    .locator("tr", { hasText: "RESULT_ISSUED" })
    .first();
  await expect(resultIssuedRow).toBeVisible();
  await resultIssuedRow.locator('[data-testid^="open-case-"]').click();

  await expect(page.getByTestId("shap-waterfall")).toBeVisible();
  await expect(page.getByTestId("survival-chart")).toBeVisible();

  // 4. Advance RESULT_ISSUED -> PATIENT_NOTIFIED so patient can acknowledge
  await page.getByTestId("advance-state-select").selectOption("PATIENT_NOTIFIED");
  await page.getByTestId("advance-evidence-input").fill("message_sent");
  await page.getByTestId("advance-state-btn").click();
  await expect(page.getByTestId("case-current-state")).toContainText(
    "PATIENT_NOTIFIED"
  );

  // 5. Switch to mobile 375px viewport for Patient Portal (R3: EN/HI/ES, Acknowledge, Teach-Back)
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByTestId("patient-portal-link").click();
  await expect(page).toHaveURL(/\/p\/pt-/);
  await expect(page.getByTestId("patient-3-step-tracker")).toBeVisible();

  // Switch languages EN -> HI -> ES -> EN
  await page.getByTestId("lang-btn-hi").click();
  await expect(page.getByTestId("patient-message-body")).toBeVisible();
  await page.getByTestId("lang-btn-es").click();
  await expect(page.getByTestId("patient-message-body")).toBeVisible();
  await page.getByTestId("lang-btn-en").click();

  // Click "I understand" acknowledge button
  await page.getByTestId("patient-acknowledge-btn").click();
  await expect(page.getByTestId("ack-confirmed-badge")).toBeVisible();

  // Submit teach-back
  await page.getByTestId("submit-teachback-btn").click();
  await expect(page.getByTestId("teachback-result-banner")).toBeVisible();

  // 6. Back to desktop 1280px: find a SEEN case in queue and test closure gate (R5)
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/app/queue");
  const seenRow = page.locator("tr", { hasText: "SEEN" }).first();
  await expect(seenRow).toBeVisible();
  await seenRow.locator('[data-testid^="open-case-"]').click();
  await expect(page.getByTestId("case-current-state")).toContainText("SEEN");

  // Attempt closure WITHOUT evidence -> must show 409 error banner
  await page.getByTestId("close-case-btn").click();
  await expect(page.getByTestId("closure-error-banner")).toContainText("409");

  // Select allowed closure evidence (treatment_started) and close case -> succeeds
  await page.getByTestId("evidence-checkbox-treatment_started").check();
  await page.getByTestId("close-case-btn").click();
  await expect(page.getByTestId("closure-success-banner")).toContainText(
    "CLOSED"
  );

  // 7. Advance sandbox time (+48h) and verify clock badge updates
  await page.getByTestId("advance-time-btn").click();
  await expect(page.getByTestId("clock-offset-badge")).toContainText("+48h");

  // 8. Visit Metrics & Model Card pages
  await page.goto("/app/metrics");
  await expect(page.getByTestId("metrics-kpi-grid")).toBeVisible();
  await expect(page.getByTestId("simulation-panel")).toBeVisible();

  await page.goto("/app/model-card");
  await expect(page.getByTestId("model-version-badge")).toBeVisible();
  await expect(page.getByTestId("model-roc-auc")).toBeVisible();
});
