import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Card,
  Typography,
  Progress,
  Space,
  Button,
  Tag,
  Statistic,
  Row,
  Col,
  Divider,
  Alert,
  Spin,
} from 'antd';
import {
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  CloudServerOutlined,
} from '@ant-design/icons';
import { getIndexingStatus, checkHealth } from '../../api';

const { Text, Title, Paragraph } = Typography;

const STAGE_TEXT = {
  starting: '初始化',
  embedding_chunks: '文档嵌入',
  openie: '实体与关系抽取',
  embedding_entities: '实体嵌入',
  embedding_facts: '事实嵌入',
  graph_construction: '知识图谱构建',
  completed: '完成',
  failed: '失败',
};

const STATUS_META = {
  idle: { label: '空闲', color: 'default', icon: <PauseCircleOutlined /> },
  indexing: { label: '索引进行中', color: 'processing', icon: <SyncOutlined spin /> },
  completed: { label: '已完成', color: 'success', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: 'error', icon: <CloseCircleOutlined /> },
};

const STAGE_WEIGHT = {
  starting: 48,
  embedding_chunks: 58,
  openie: 68,
  embedding_entities: 75,
  embedding_facts: 82,
  graph_construction: 90,
  completed: 100,
};

const IngestStatus = () => {
  const [loading, setLoading] = useState(true);
  const [statusPayload, setStatusPayload] = useState(null);
  const [healthPayload, setHealthPayload] = useState(null);
  const [sseData, setSseData] = useState(null);
  const [lastFetch, setLastFetch] = useState(null);
  const [sseConnected, setSseConnected] = useState(false);
  const eventSourceRef = useRef(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      const [st, hl] = await Promise.all([getIndexingStatus(), checkHealth()]);
      setStatusPayload(st.data);
      setHealthPayload(hl.data);
      setLastFetch(new Date());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSnapshot();
    const id = setInterval(fetchSnapshot, 5000);
    return () => clearInterval(id);
  }, [fetchSnapshot]);

  const indexingStatus = statusPayload?.indexing_status;

  const closeSse = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setSseConnected(false);
  }, []);

  useEffect(() => {
    if (indexingStatus === 'indexing') {
      const apiBaseUrl = process.env.REACT_APP_API_URL || '/api';
      const es = new EventSource(`${apiBaseUrl}/index/progress`);
      eventSourceRef.current = es;
      setSseConnected(true);

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setSseData(data);
        } catch (err) {
          console.error('SSE parse error', err);
        }
      };

      es.onerror = () => {
        setSseConnected(false);
        es.close();
        eventSourceRef.current = null;
      };

      return () => {
        es.close();
        eventSourceRef.current = null;
        setSseConnected(false);
      };
    }
    closeSse();
    if (indexingStatus === 'idle') {
      setSseData(null);
    }
    return undefined;
  }, [indexingStatus, closeSse]);

  const effectiveStatus = sseData?.status ?? statusPayload?.indexing_status ?? 'idle';
  const messageText = sseData?.message ?? statusPayload?.message ?? '';
  const progress = sseData?.progress;
  const meta = STATUS_META[effectiveStatus] || STATUS_META.idle;

  let percent = 0;
  if (progress?.total_docs > 0 && progress?.processed_docs != null) {
    percent = Math.round((progress.processed_docs / progress.total_docs) * 100);
  } else if (progress?.current_stage && STAGE_WEIGHT[progress.current_stage] != null) {
    percent = Math.min(99, STAGE_WEIGHT[progress.current_stage]);
  }

  return (
    <div>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={4} style={{ marginTop: 0 }}>
            <CloudServerOutlined style={{ marginRight: 8 }} />
            索引任务状态
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            页面会轮询接口并自动连接实时进度（SSE）。刷新或离开「文档上传」页后，可在此查看后台 ingest 是否仍在进行。
          </Paragraph>
        </div>

        <Card
          title="当前状态"
          extra={
            <Button icon={<ReloadOutlined />} onClick={() => fetchSnapshot()} loading={loading}>
              刷新
            </Button>
          }
        >
          {loading && !statusPayload ? (
            <Spin />
          ) : (
            <>
              <Row gutter={[16, 16]}>
                <Col xs={24} sm={12} md={8}>
                  <Statistic
                    title="索引状态"
                    value={meta.label}
                    prefix={meta.icon}
                  />
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <Statistic
                    title="HippoRAG"
                    value={healthPayload?.hipporag_initialized ? '已初始化' : '未初始化'}
                  />
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <Statistic
                    title="实时通道 (SSE)"
                    value={sseConnected ? '已连接' : effectiveStatus === 'indexing' ? '连接中…' : '未连接'}
                  />
                </Col>
              </Row>
              <Divider style={{ margin: '16px 0' }} />
              <Space wrap>
                <Tag color={meta.color}>API: {effectiveStatus}</Tag>
                {lastFetch && (
                  <Text type="secondary">
                    最近同步：{lastFetch.toLocaleString()}
                  </Text>
                )}
              </Space>
              {messageText && (
                <Paragraph style={{ marginTop: 12, marginBottom: 0 }}>
                  <Text strong>消息：</Text> {messageText}
                </Paragraph>
              )}
            </>
          )}
        </Card>

        {(effectiveStatus === 'indexing' || progress?.current_stage) && (
          <Card title="进度详情">
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="阶段"
                  value={STAGE_TEXT[progress?.current_stage] || progress?.current_stage || '—'}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="已处理 / 总数"
                  value={progress?.processed_docs ?? 0}
                  suffix={`/ ${progress?.total_docs ?? 0}`}
                />
              </Col>
              <Col span={8}>
                <Statistic title="进度条" value={`${Math.min(100, percent)}%`} />
              </Col>
            </Row>
            <Progress
              percent={Math.min(100, percent)}
              status={effectiveStatus === 'failed' ? 'exception' : 'active'}
              style={{ marginTop: 16 }}
            />
            {progress?.error && (
              <Alert
                type="error"
                message={progress.error}
                style={{ marginTop: 16 }}
                showIcon
              />
            )}
          </Card>
        )}

        {effectiveStatus === 'idle' && !loading && (
          <Alert
            type="info"
            showIcon
            message="当前没有正在运行的索引任务"
            description="在「文档上传」页提交任务后，可回到本页查看进度；若任务已在后台完成，此处会显示为空闲或最近一次结果（取决于服务端状态是否已重置）。"
          />
        )}
      </Space>
    </div>
  );
};

export default IngestStatus;
