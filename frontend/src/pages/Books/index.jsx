import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, Space, message, Tag, Popconfirm } from 'antd';
import { PlusOutlined, DeleteOutlined, BookOutlined } from '@ant-design/icons';
import { getBooks, createBook, deleteBook } from '../../api';

const Books = () => {
  const [loading, setLoading] = useState(false);
  const [books, setBooks] = useState([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();

  const fetchBooks = async () => {
    try {
      setLoading(true);
      const res = await getBooks();
      setBooks(res.data.books || []);
    } catch (err) {
      message.error('获取书籍列表失败');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBooks();
  }, []);

  const handleCreate = async (values) => {
    try {
      await createBook(values.book_id);
      message.success('创建成功');
      setModalVisible(false);
      form.resetFields();
      fetchBooks();
    } catch (err) {
      message.error(err.response?.data?.detail || '创建失败');
    }
  };

  const handleDelete = async (bookId) => {
    try {
      await deleteBook(bookId);
      message.success('删除成功');
      fetchBooks();
    } catch (err) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    {
      title: 'Book ID',
      dataIndex: 'book_id',
      key: 'book_id',
      render: (text) => (
        <span>
          <BookOutlined style={{ marginRight: 8 }} />
          {text}
        </span>
      ),
    },
    {
      title: '文档数量',
      dataIndex: 'doc_count',
      key: 'doc_count',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => (
        <Tag color={status === 'ready' ? 'green' : 'orange'}>
          {status === 'ready' ? '就绪' : '索引中'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text) => text ? new Date(text).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title="确定删除此书籍？"
          description="删除后将无法恢复，相关的索引数据也会被清除。"
          onConfirm={() => handleDelete(record.book_id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalVisible(true)}
        >
          创建书籍
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={books}
        rowKey="book_id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="创建书籍"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="book_id"
            label="Book ID"
            rules={[
              { required: true, message: '请输入 Book ID' },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符' },
            ]}
          >
            <Input placeholder="例如: novel_001" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Books;
