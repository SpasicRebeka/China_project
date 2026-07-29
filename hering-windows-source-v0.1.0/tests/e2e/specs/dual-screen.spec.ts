import { expect, test } from '@playwright/test'

async function expectFixedViewport(page: import('@playwright/test').Page) {
  await expect.poll(() => page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    height: document.documentElement.scrollHeight,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
  }))).toEqual({
    width: 1024,
    height: 600,
    viewportWidth: 1024,
    viewportHeight: 600,
  })
}

test('doctor and patient complete one structured question at 1024 by 600', async ({ browser }) => {
  const screen = { viewport: { width: 1024, height: 600 }, hasTouch: true }
  const doctorContext = await browser.newContext(screen)
  const patientContext = await browser.newContext(screen)
  const doctor = await doctorContext.newPage()
  const patient = await patientContext.newPage()

  await doctor.goto('/doctor/')
  await expect(doctor.getByText('连接正常')).toBeVisible()
  const patientUrl = await doctor.locator('.join-panel code').innerText()

  await patient.goto(patientUrl)
  await expect(patient.getByText('患者端')).toBeVisible()
  await expect(patient.getByRole('heading', { name: '已连接，请等待医生提问' })).toBeVisible()
  await expectFixedViewport(patient)

  await doctor.locator('.network-node--complaint').filter({ hasText: '胸闷' }).click()
  await doctor.locator('.network-node--question').first().click()
  await doctor.getByRole('button', { name: '发送问题' }).click()

  await expect(patient.getByRole('heading', { name: '你现在还有这个不适吗？' })).toBeVisible()
  await expectFixedViewport(patient)
  await patient.getByRole('button', { name: '现在还有' }).click()
  await patient.getByRole('button', { name: '确认提交' }).click()

  await expect(patient.getByRole('heading', { name: '现在还有' })).toBeVisible()
  await expect(doctor.getByText('患者回答：现在还有', { exact: true })).toBeVisible()
  await expectFixedViewport(patient)

  await doctor.getByRole('button', { name: '确认回答' }).click()
  await expect(patient.getByText('医生已收到并确认').first()).toBeVisible()

  await doctorContext.close()
  await patientContext.close()
})
