<template>
  <section class="page" data-module="abnormal">
    <header class="page-head">
      <div>
        <h2>不符合项管理</h2>
        <p class="page-desc">维护不符合项，围绕不符合编号、发现环节、不符合描述、严重程度做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记不符合项</button>
        <button class="btn" type="button" @click="exportRows">导出不符合项清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>不符合编号</span>
        <input v-model="filters.keyword" placeholder="按不符合编号检索" />
      </label>
      <label class="filter-item">
        <span>处置状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-if="nextAction(row)"
              class="link"
              type="button"
              @click="openAction(row)"
            >
              {{ nextAction(row) }}
            </button>
            <span v-else class="closed-note">已关闭，仅可查看</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无不符合项数据，可先登记不符合项</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条不符合项记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailEntry" class="dialog-mask" @click.self="closeDetail">
      <div class="dialog">
        <h3>不符合项详情 · {{ detailEntry['不符合编号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="field in columns" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detailEntry[field] || '—' }}</dd>
          </template>
        </dl>
        <footer class="dialog-foot">
          <button
            v-if="nextAction(detailEntry)"
            class="btn primary"
            type="button"
            @click="openAction(detailEntry)"
          >
            {{ nextAction(detailEntry) }}
          </button>
          <span v-else class="closed-note">已关闭，仅可查看</span>
          <button class="btn" type="button" @click="closeDetail">返回列表</button>
        </footer>
      </div>
    </div>

    <div v-if="actionDialog" class="dialog-mask" @click.self="closeAction">
      <form class="dialog" @submit.prevent="submitAction">
        <h3>{{ actionDialog.action }} · {{ actionDialog.entry['不符合编号'] }}</h3>
        <p class="dialog-desc">
          当前处置状态：{{ actionDialog.entry['处置状态'] }}；本次只保存「{{ actionDialog.field }}」到该编号，不影响其他字段。
        </p>
        <label class="dialog-field">
          <span>{{ actionDialog.field }}</span>
          <textarea
            v-model="actionDialog.value"
            rows="4"
            :placeholder="`请填写${actionDialog.field}`"
          ></textarea>
        </label>
        <p v-if="actionDialog.error" class="error-text">{{ actionDialog.error }}</p>
        <footer class="dialog-foot">
          <button class="btn ghost" type="button" @click="closeAction">取消</button>
          <button class="btn primary" type="submit" :disabled="actionDialog.saving">
            保存并{{ actionDialog.action }}
          </button>
        </footer>
      </form>
    </div>

    <div v-if="createDialog" class="dialog-mask" @click.self="createDialog = null">
      <form class="dialog" @submit.prevent="submitCreate">
        <h3>登记不符合项</h3>
        <label v-for="field in createFields" :key="field" class="dialog-field">
          <span>{{ field }}</span>
          <input v-model="createDialog.values[field]" :placeholder="`请填写${field}`" />
        </label>
        <p v-if="createDialog.error" class="error-text">{{ createDialog.error }}</p>
        <footer class="dialog-foot">
          <button class="btn ghost" type="button" @click="createDialog = null">取消</button>
          <button class="btn primary" type="submit" :disabled="createDialog.saving">提交登记</button>
        </footer>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/abnormal'
const columns = ["不符合编号", "发现环节", "不符合描述", "严重程度", "原因分析", "纠正措施", "验证人员", "处置状态"]
const statuses = ["待分析", "待纠正", "待验证", "已关闭"]
const createFields = ["不符合编号", "发现环节", "不符合描述", "严重程度"]
// 每个动作只负责自己的字段：分析原因→原因分析，实施纠正→纠正措施，验证关闭→验证人员
const ACTION_FIELDS: Record<string, string> = { 分析原因: '原因分析', 实施纠正: '纠正措施', 验证关闭: '验证人员' }
const NEXT_ACTION: Record<string, string> = { 待分析: '分析原因', 待纠正: '实施纠正', 待验证: '验证关闭' }

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref({ keyword: '', status: '' })
const stats = ref([
  { label: '待分析不符合', value: 0 },
  { label: '待纠正不符合', value: 0 },
  { label: '已关闭不符合', value: 0 },
])

// 详情与处置弹窗各自持有按 id 拉取的记录副本，关掉即清空，不会串到上一条
const detailEntry = ref<Row | null>(null)
const actionDialog = ref<{
  action: string
  field: string
  entry: Row
  value: string
  error: string
  saving: boolean
} | null>(null)
const createDialog = ref<{
  values: Record<string, string>
  error: string
  saving: boolean
} | null>(null)

function nextAction(row: Row): string {
  return NEXT_ACTION[String(row['处置状态'] ?? '')] ?? ''
}

async function fetchEntry(id: string | number | null): Promise<Row> {
  const response = await request(`${ENDPOINT}/${id}`)
  const payload = await response.json()
  if (!response.ok) {
    throw new Error(payload.detail ?? '不符合项详情读取失败')
  }
  return payload as Row
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    detailEntry.value = await fetchEntry(row.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '不符合项详情读取失败'
  }
}

function closeDetail() {
  detailEntry.value = null
}

async function openAction(row: Row) {
  const action = nextAction(row)
  if (!action) {
    return
  }
  errorMessage.value = ''
  try {
    // 打开弹窗时按 id 重新拉取，预填的是这条编号自己已保存的内容
    const entry = await fetchEntry(row.id)
    const field = ACTION_FIELDS[action]
    actionDialog.value = {
      action,
      field,
      entry,
      value: String(entry[field] ?? ''),
      error: '',
      saving: false,
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '不符合项详情读取失败'
  }
}

function closeAction() {
  actionDialog.value = null
}

async function submitAction() {
  const dialog = actionDialog.value
  if (!dialog || dialog.saving) {
    return
  }
  const value = dialog.value.trim()
  if (!value) {
    dialog.error = dialog.action === '验证关闭'
      ? '验证人员为空，不允许关闭：请先填写验证人员'
      : `${dialog.field}为空，请先填写再${dialog.action}`
    return
  }
  dialog.saving = true
  dialog.error = ''
  try {
    const response = await request(`${ENDPOINT}/${dialog.entry.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action: dialog.action, [dialog.field]: value }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '不符合项动作未生效，请稍后重试')
    }
    actionDialog.value = null
    // 详情若正打开同一条，跟着服务端返回的结论一起刷新，三处保持一致
    if (detailEntry.value && payload.entry && detailEntry.value.id === payload.entry.id) {
      detailEntry.value = payload.entry
    }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '不符合项操作失败'
  } finally {
    dialog.saving = false
  }
}

function openCreate() {
  createDialog.value = {
    values: { 不符合编号: '', 发现环节: '', 不符合描述: '', 严重程度: '' },
    error: '',
    saving: false,
  }
}

async function submitCreate() {
  const dialog = createDialog.value
  if (!dialog || dialog.saving) {
    return
  }
  dialog.saving = true
  dialog.error = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: dialog.values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '不符合项登记失败')
    }
    createDialog.value = null
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '不符合项登记失败'
  } finally {
    dialog.saving = false
  }
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword.trim()) {
    query.set('keyword', filters.value.keyword.trim())
  }
  if (filters.value.status) {
    query.set('status', filters.value.status)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.detail ?? '不符合项列表读取失败')
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '不符合项列表读取失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    const payload = await response.json()
    if (!response.ok) {
      return
    }
    const all: Row[] = payload.items ?? []
    const count = (status: string) => all.filter((row) => row['处置状态'] === status).length
    stats.value = [
      { label: '待分析不符合', value: count('待分析') },
      { label: '待纠正不符合', value: count('待纠正') },
      { label: '已关闭不符合', value: count('已关闭') },
    ]
  } catch {
    // 统计卡片失败不阻断列表
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
