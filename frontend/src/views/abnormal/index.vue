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
          <option value="">全部</option>
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
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="isClosed(row)" class="readonly-tip">已关闭，仅供查询</span>
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

    <!-- 详情弹窗：只读展示，已关闭的记录也能查 -->
    <div v-if="detailRow" class="modal-mask" @click.self="closeDetail">
      <div class="modal-panel">
        <h3 class="modal-title">不符合项详情 — {{ detailRow['不符合编号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detailRow[field] || '—' }}</dd>
          </template>
        </dl>
        <p v-if="isClosed(detailRow)" class="readonly-tip">该不符合项已关闭，仅供查询，不能再改动。</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeDetail">返回列表</button>
        </div>
      </div>
    </div>

    <!-- 处置弹窗：每次打开都重新取当前这条记录，不沿用上一条填写的内容 -->
    <div v-if="actionDialog" class="modal-mask" @click.self="closeAction">
      <form class="modal-panel" @submit.prevent="submitAction">
        <h3 class="modal-title">{{ actionDialog.action }} — {{ actionDialog.code }}</h3>
        <p class="readonly-tip">当前处置状态：{{ actionDialog.conclusion }}</p>
        <label class="form-item">
          <span>{{ actionDialog.field }}</span>
          <textarea v-model="actionDialog.value" rows="4" :placeholder="`请填写${actionDialog.field}`"></textarea>
        </label>
        <p v-if="actionDialog.error" class="error-text">{{ actionDialog.error }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeAction">取消</button>
          <button class="btn primary" type="submit" :disabled="actionDialog.submitting">
            确认{{ actionDialog.action }}
          </button>
        </div>
      </form>
    </div>

    <!-- 登记弹窗 -->
    <div v-if="createDialog" class="modal-mask" @click.self="closeCreate">
      <form class="modal-panel" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记不符合项</h3>
        <label v-for="field in createFields" :key="field" class="form-item">
          <span>{{ field }}</span>
          <input v-model="createDialog.values[field]" :placeholder="`请填写${field}`" />
        </label>
        <p v-if="createDialog.error" class="error-text">{{ createDialog.error }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="submit" :disabled="createDialog.submitting">确认登记</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/abnormal'
const columns = ["不符合编号", "发现环节", "不符合描述", "严重程度", "原因分析", "纠正措施", "验证人员", "处置状态"]
const detailFields = columns
const statuses = ["待分析", "待纠正", "待验证", "已关闭"]
const createFields = ["不符合编号", "发现环节", "不符合描述", "严重程度"]
// 每个动作只保存自己负责的字段，原因分析、纠正措施、验证人员分开落库，互不覆盖
const ACTION_FIELDS: Record<string, string> = { "分析原因": "原因分析", "实施纠正": "纠正措施", "验证关闭": "验证人员" }
const STATUS_ACTIONS: Record<string, string[]> = { "待分析": ["分析原因"], "待纠正": ["实施纠正"], "待验证": ["验证关闭"], "已关闭": [] }

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref({ keyword: '', status: '' })

const stats = computed(() => [
  { label: '待分析不符合', value: countByStatus('待分析') },
  { label: '待纠正不符合', value: countByStatus('待纠正') },
  { label: '已关闭不符合', value: countByStatus('已关闭') },
])

function countByStatus(status: string) {
  return rows.value.filter((row) => row.status === status).length
}

function isClosed(row: Row) {
  return row.status === '已关闭'
}

function rowActions(row: Row) {
  return STATUS_ACTIONS[String(row.status)] ?? []
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

const detailRow = ref<Row | null>(null)

async function fetchEntry(entryId: string | number): Promise<Row> {
  const response = await request(`${ENDPOINT}/${entryId}`)
  if (!response.ok) {
    throw new Error('不符合项详情读取失败')
  }
  return (await response.json()) as Row
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    detailRow.value = await fetchEntry(Number(row.id))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '不符合项详情读取失败'
  }
}

function closeDetail() {
  detailRow.value = null
}

interface ActionDialog {
  action: string
  field: string
  entryId: number
  code: string
  conclusion: string
  value: string
  error: string
  submitting: boolean
}

const actionDialog = ref<ActionDialog | null>(null)

async function openAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    // 先取这条记录的最新内容，弹窗只填它自己编号下的字段，不带入上一条的数据
    const entry = await fetchEntry(Number(row.id))
    const field = ACTION_FIELDS[action]
    actionDialog.value = {
      action,
      field,
      entryId: Number(entry.id),
      code: String(entry['不符合编号'] ?? ''),
      conclusion: String(entry['处置状态'] ?? ''),
      value: String(entry[field] ?? ''),
      error: '',
      submitting: false,
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '不符合项操作失败'
  }
}

function closeAction() {
  actionDialog.value = null
}

async function submitAction() {
  const dialog = actionDialog.value
  if (!dialog) return
  if (!dialog.value.trim()) {
    dialog.error = `${dialog.field}为空，不能${dialog.action}：请先填写${dialog.field}`
    return
  }
  dialog.error = ''
  dialog.submitting = true
  try {
    const response = await request(`${ENDPOINT}/${dialog.entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: dialog.action, [dialog.field]: dialog.value.trim() } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? result.detail ?? '不符合项动作未生效，请稍后重试')
    }
    actionDialog.value = null
    await reload()
    if (detailRow.value && Number(detailRow.value.id) === dialog.entryId) {
      // 详情还开着的话同步刷新，保证列表、详情、弹窗看到的结论一致
      detailRow.value = await fetchEntry(dialog.entryId)
    }
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '不符合项操作失败'
  } finally {
    dialog.submitting = false
  }
}

interface CreateDialog {
  values: Record<string, string>
  error: string
  submitting: boolean
}

const createDialog = ref<CreateDialog | null>(null)

function openCreate() {
  createDialog.value = { values: {}, error: '', submitting: false }
}

function closeCreate() {
  createDialog.value = null
}

async function submitCreate() {
  const dialog = createDialog.value
  if (!dialog) return
  dialog.error = ''
  dialog.submitting = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: dialog.values }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? result.detail ?? '不符合项登记失败')
    }
    createDialog.value = null
    await reload()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '不符合项登记失败'
  } finally {
    dialog.submitting = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword.trim()) query.set('keyword', filters.value.keyword.trim())
  if (filters.value.status) query.set('status', filters.value.status)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('不符合项列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '不符合项列表读取失败'
  }
}

onMounted(reload)
</script>
