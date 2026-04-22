<template>
  <div class="page-shell">
    <PageHeader :title="text.pageTitle" :description="text.pageDesc">
      <el-button @click="loadAll">{{ text.refresh }}</el-button>
      <el-button type="primary" @click="router.push('/assistant')">{{ text.backAssistant }}</el-button>
    </PageHeader>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">{{ text.resumeCount }}</div>
        <div class="stat-value">{{ resumes.length || resumeAttachments.length }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">{{ text.experienceCount }}</div>
        <div class="stat-value">{{ projects.length + internships.length }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">{{ text.achievementCount }}</div>
        <div class="stat-value">{{ certificates.length + competitions.length + campusExperiences.length }}</div>
      </div>
      <div class="stat-card highlight">
        <div class="stat-label">{{ text.currentTarget }}</div>
        <div class="stat-value small">{{ optimization?.target_role || ingestResult?.parsed_resume?.target_role || parsedResume?.target_role || text.pending }}</div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="tabs">
      <el-tab-pane :label="text.resumeTab" name="resume">
        <div class="resume-manager grid two">
          <SectionCard :title="text.resumeLibraryTitle || '多简历管理'">
            <div class="row-between" style="margin-bottom: 12px">
              <div class="hint">支持多份简历与多版本</div>
            </div>
            <div class="resume-actions">
              <div class="action-group">
                <el-button size="small" type="primary" @click="openCreateResumePrompt">新建简历</el-button>
                <el-button size="small" :disabled="!activeAttachment" @click="createResumeFromSelectedAttachment">从附件创建</el-button>
              </div>
              <div class="action-group" v-if="activeResume">
                <el-button size="small" @click="cloneActiveResume">复制</el-button>
                <el-button size="small" :disabled="activeResume.is_default" @click="setActiveResumeDefault">设为默认</el-button>
                <el-button size="small" type="danger" @click="deleteActiveResume">删除</el-button>
              </div>
            </div>
            <el-empty v-if="!resumes.length" description="暂无简历实体，可先上传附件并创建。" />
            <div v-else class="stack">
              <div
                v-for="item in resumes"
                :key="`resume-${item.id}`"
                :class="['resume-item', { active: item.id === activeResumeId }]"
                @click="selectResume(item)"
              >
                <div class="row-between">
                  <strong>{{ item.title || `简历${item.id}` }}</strong>
                  <el-tag size="small" :type="item.is_default ? 'success' : 'info'">{{ item.is_default ? '默认' : `V${item.current_version?.version_no || '-'}` }}</el-tag>
                </div>
                <div class="hint">岗位：{{ item.target_job || '-' }} ｜ 城市：{{ item.target_city || '-' }}</div>
                <div class="hint">更新时间：{{ item.updated_at || '-' }}</div>
              </div>
            </div>
          </SectionCard>

          <SectionCard :title="text.resumeDetailTitle || '当前简历详情'">
            <el-empty v-if="!activeResume" description="请先选择左侧简历" />
            <div v-else class="stack">
              <div class="row-between detail-header">
                <div>
                  <div class="title small-title">{{ activeResume.title }}</div>
                  <div class="hint">
                    岗位 {{ activeResume.target_job || '-' }} ｜ 行业 {{ activeResume.target_industry || '-' }} ｜ 城市 {{ activeResume.target_city || '-' }}
                  </div>
                </div>
                <div class="detail-actions">
                  <el-button size="small" type="primary" :loading="optimizing" @click="optimizeActiveResume">优化并存新版本</el-button>
                  <el-dropdown trigger="click">
                    <el-button size="small">更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item @click="openEditResumePrompt">编辑</el-dropdown-item>
                        <el-dropdown-item :disabled="!activeAttachment" @click="createVersionFromCurrentAttachment">当前附件存为新版本</el-dropdown-item>
                        <el-dropdown-item divided :disabled="!activeResume && !activeAttachment" @click="router.push('/student/resume-delivery')">投递</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>

              <div class="version-list">
                <div class="block-title">版本列表</div>
                <el-empty v-if="!activeResumeVersions.length" description="暂无版本" />
                <div v-else class="stack">
                  <div
                    v-for="version in activeResumeVersions"
                    :key="`version-${version.id}`"
                    :class="['resume-item', { active: version.id === activeResumeVersionId }]"
                    @click="selectResumeVersion(version)"
                  >
                    <div class="row-between">
                      <strong>V{{ version.version_no }}</strong>
                      <el-tag size="small" :type="version.is_active ? 'success' : 'info'">{{ version.is_active ? '当前' : '历史' }}</el-tag>
                    </div>
                    <div class="hint">{{ version.change_summary || '-' }}</div>
                    <div class="hint">{{ version.attachment?.file_name || '无附件版本' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>
        </div>

        <div class="grid two">
          <SectionCard :title="text.uploadSection">
            <div class="stack">
              <el-upload
                accept=".png,.jpg,.jpeg,.webp,.bmp,.pdf,.doc,.docx"
                :auto-upload="false"
                :on-change="handleChange"
                :show-file-list="false"
              >
                <el-button type="primary" plain>{{ text.pickResume }}</el-button>
              </el-upload>
              <div class="hint">{{ text.currentFile }}{{ uploadFile?.name || text.noFile }}</div>
              <el-input v-model="uploadDescription" :placeholder="text.uploadDescPlaceholder" />
              <el-switch
                v-model="uploadCreateResume"
                inline-prompt
                active-text="上传后创建简历"
                inactive-text="仅保存附件"
              />
              <el-button type="success" :disabled="!uploadFile" :loading="uploading" @click="uploadResume">{{ text.upload }}</el-button>

              <el-empty v-if="!resumeAttachments.length" :description="text.emptyResume" />
              <div v-else class="stack">
                <div
                  v-for="item in resumeAttachments"
                  :key="item.id"
                  :class="['resume-item', { active: item.id === activeAttachmentId }]"
                  @click="selectAttachment(item)"
                >
                  <div class="row-between">
                    <strong>{{ item.file_name }}</strong>
                    <el-tag size="small">{{ (item.file_type || '-').toUpperCase() }}</el-tag>
                  </div>
                  <div class="hint">{{ item.description || text.noDesc }}</div>
                  <div class="mini-actions" @click.stop>
                    <el-button link type="primary" @click="parseAttachment(item)">{{ text.parse }}</el-button>
                    <el-button link type="warning" @click="ingestAttachment(item)">{{ text.ingest }}</el-button>
                    <el-button link type="primary" @click="previewAttachment(item)">{{ text.preview }}</el-button>
                    <el-button link type="success" @click="optimizeAttachment(item)">{{ text.optimize }}</el-button>
                    <el-button link type="danger" @click="removeAttachment(item)">{{ text.remove }}</el-button>
                  </div>
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard :title="text.resultSection">
            <el-empty v-if="!activeAttachment" :description="text.selectResumeFirst" />
            <div v-else class="stack">
              <div class="row-between">
                <div>
                  <div class="title">{{ activeAttachment.file_name }}</div>
                  <div class="hint">{{ text.parserEngine }}{{ parsedResume?.parser_engine || ingestResult?.parsed_resume?.parser_engine || text.notParsed }}</div>
                </div>
                <div class="mini-actions">
                  <el-button :loading="parsing" @click="parseAttachment(activeAttachment)">{{ text.parseResume }}</el-button>
                  <el-button :loading="ingesting" type="warning" @click="ingestAttachment(activeAttachment)">{{ text.ingest }}</el-button>
                  <el-button :loading="optimizing" type="primary" @click="optimizeAttachment(activeAttachment)">{{ text.optimize }}</el-button>
                  <el-button type="success" plain @click="router.push('/student/resume-delivery')">{{ text.deliverResume }}</el-button>
                  <el-button @click="downloadCurrentWord">{{ text.downloadWord }}</el-button>
                  <el-button @click="downloadCurrentPdf">{{ text.downloadPdf }}</el-button>
                  <el-button type="success" plain @click="router.push('/profile/radar')">{{ text.viewProfile }}</el-button>
                </div>
              </div>

              <div v-if="optimization" class="score-grid">
                <div class="score-card"><span>{{ text.resumeScore }}</span><strong>{{ optimization.resume_score }}</strong></div>
                <div class="score-card"><span>{{ text.keywordScore }}</span><strong>{{ optimization.keyword_match_score }}</strong></div>
                <div class="score-card"><span>{{ text.richnessScore }}</span><strong>{{ optimization.content_richness_score }}</strong></div>
                <div class="score-card"><span>{{ text.projectScore }}</span><strong>{{ optimization.project_evidence_score }}</strong></div>
              </div>
              <div v-if="optimization" class="tag-wrap">
                <el-tag :type="optimization.llm_used ? 'success' : 'warning'" round>
                  {{ optimization.llm_used ? text.deepOptimizeOn : text.deepOptimizeFallback }}
                </el-tag>
              </div>

              <SectionCard v-if="ingestResult" :title="text.ingestResultTitle">
                <div class="stack">
                  <div class="hint">{{ text.ingestDone }}</div>
                  <div class="tag-wrap">
                    <el-tag type="warning" round>{{ text.updatedFields }}{{ ingestSummary.updatedFields.join(' / ') || text.none }}</el-tag>
                    <el-tag round>{{ text.newSkills }}{{ ingestSummary.skillsAdded }}</el-tag>
                    <el-tag round>{{ text.newCerts }}{{ ingestSummary.certificatesAdded }}</el-tag>
                    <el-tag round>{{ text.newProjects }}{{ ingestSummary.projectsAdded }}</el-tag>
                    <el-tag round>{{ text.newInternships }}{{ ingestSummary.internshipsAdded }}</el-tag>
                  </div>
                  <p>{{ ingestResult.profile?.summary || text.profileReady }}</p>
                </div>
              </SectionCard>

              <SectionCard :title="text.parseSummary">
                <p>{{ optimization?.parsed_resume?.summary || parsedResume?.summary || text.noParsedContent }}</p>
              </SectionCard>

              <div class="grid two fit-grid">
                <SectionCard :title="text.basicInfo">
                  <div class="info-list">
                    <div><span>{{ text.name }}</span><strong>{{ parsedResume?.name || '-' }}</strong></div>
                    <div><span>{{ text.phone }}</span><strong>{{ parsedResume?.phone || '-' }}</strong></div>
                    <div><span>{{ text.email }}</span><strong>{{ parsedResume?.email || '-' }}</strong></div>
                    <div><span>{{ text.grade }}</span><strong>{{ parsedResume?.grade || '-' }}</strong></div>
                    <div><span>{{ text.major }}</span><strong>{{ parsedResume?.major || '-' }}</strong></div>
                    <div><span>{{ text.college }}</span><strong>{{ parsedResume?.college || '-' }}</strong></div>
                    <div><span>{{ text.targetRole }}</span><strong>{{ parsedResume?.target_role || '-' }}</strong></div>
                    <div><span>{{ text.targetIndustry }}</span><strong>{{ parsedResume?.target_industry || '-' }}</strong></div>
                  </div>
                </SectionCard>

                <SectionCard :title="text.tagsTitle">
                  <div class="block-title">{{ text.skillTags }}</div>
                  <div class="tag-wrap">
                    <el-tag v-for="tag in parsedSkills" :key="`skill-${tag}`" round effect="plain">{{ tag }}</el-tag>
                  </div>
                  <div class="block-title" style="margin-top: 12px">{{ text.interestTags }}</div>
                  <div class="tag-wrap">
                    <el-tag v-for="tag in parsedInterests" :key="`interest-${tag}`" type="success" round effect="plain">{{ tag }}</el-tag>
                  </div>
                  <div class="block-title" style="margin-top: 12px">{{ text.certificateTags }}</div>
                  <div class="tag-wrap">
                    <el-tag v-for="tag in parsedCertificates" :key="`cert-${tag}`" type="warning" round effect="plain">{{ tag }}</el-tag>
                  </div>
                </SectionCard>
              </div>

              <SectionCard :title="text.optimizeSection">
                <el-empty v-if="!optimization" :description="text.clickOptimize" />
                <div v-else class="stack">
                  <div>
                    <div class="block-title">{{ text.optimizedSummary }}</div>
                    <p>{{ optimization.optimized_summary }}</p>
                  </div>
                  <div class="grid two fit-grid">
                    <div>
                      <div class="block-title">{{ text.keepHighlights }}</div>
                      <div v-for="item in optimization.highlights" :key="item" class="bullet">{{ item }}</div>
                    </div>
                    <div>
                      <div class="block-title">{{ text.fixIssues }}</div>
                      <div v-for="item in optimization.issues" :key="item" class="bullet warning">{{ item }}</div>
                    </div>
                  </div>
                  <div>
                    <div class="block-title">{{ text.keywordTags }}</div>
                    <div class="tag-wrap">
                      <el-tag v-for="tag in optimization.recommended_keywords" :key="tag" type="primary" round>{{ tag }}</el-tag>
                    </div>
                  </div>
                </div>
              </SectionCard>

              <SectionCard :title="text.fullResumeSection">
                <el-empty v-if="!optimizedResumeDocument" :description="text.clickOptimize" />
                <div v-else class="stack resume-full">
                  <div class="row-between">
                    <div class="hint">
                      {{ optimization?.llm_used ? text.deepOptimizeOn : text.deepOptimizeFallback }}
                    </div>
                    <el-button size="small" @click="copyOptimizedResume">{{ text.copyFullResume }}</el-button>
                  </div>

                  <div v-if="optimizedResumeDocument.education_experience">
                    <div class="block-title">{{ text.educationTitle }}</div>
                    <p class="pre-line">{{ optimizedResumeDocument.education_experience }}</p>
                  </div>

                  <div v-if="optimizedResumeDocument.summary">
                    <div class="block-title">{{ text.optimizedSummary }}</div>
                    <p>{{ optimizedResumeDocument.summary }}</p>
                  </div>

                  <div v-if="(optimizedResumeDocument.skills || []).length">
                    <div class="block-title">{{ text.skillTags }}</div>
                    <div class="tag-wrap">
                      <el-tag v-for="tag in optimizedResumeDocument.skills" :key="`opt-skill-${tag}`" round effect="plain">{{ tag }}</el-tag>
                    </div>
                  </div>

                  <div v-if="(optimizedResumeDocument.projects || []).length">
                    <div class="block-title">{{ text.projectSection }}</div>
                    <div v-for="(item, idx) in optimizedResumeDocument.projects" :key="`opt-project-${idx}`" class="resume-entry">
                      <div class="entry-title">{{ formatProjectTitle(item) }}</div>
                      <div v-if="item.rewrite" class="entry-body">{{ item.rewrite }}</div>
                    </div>
                  </div>

                  <div v-if="(optimizedResumeDocument.internships || []).length">
                    <div class="block-title">{{ text.internshipSection }}</div>
                    <div v-for="(item, idx) in optimizedResumeDocument.internships" :key="`opt-intern-${idx}`" class="resume-entry">
                      <div class="entry-title">{{ formatInternshipTitle(item) }}</div>
                      <div v-if="item.rewrite" class="entry-body">{{ item.rewrite }}</div>
                    </div>
                  </div>

                  <div v-if="(optimizedResumeDocument.competitions || []).length">
                    <div class="block-title">{{ text.competitionSection }}</div>
                    <div v-for="(item, idx) in optimizedResumeDocument.competitions" :key="`opt-comp-${idx}`" class="resume-entry">
                      <div class="entry-title">{{ formatCompetitionTitle(item) }}</div>
                      <div v-if="item.description" class="entry-body">{{ item.description }}</div>
                    </div>
                  </div>

                  <div v-if="(optimizedResumeDocument.campus_experiences || []).length">
                    <div class="block-title">{{ text.campusSection }}</div>
                    <div v-for="(item, idx) in optimizedResumeDocument.campus_experiences" :key="`opt-campus-${idx}`" class="resume-entry">
                      <div class="entry-title">{{ formatCampusTitle(item) }}</div>
                      <div v-if="item.description" class="entry-body">{{ item.description }}</div>
                    </div>
                  </div>
                </div>
              </SectionCard>
            </div>
          </SectionCard>
        </div>

        <SectionCard :title="text.previewSection" style="margin-top: 16px">
          <el-empty v-if="!activeAttachment" :description="text.previewHint" />
          <div v-else-if="previewImages.length" class="preview-grid">
            <el-image
              v-for="image in previewImages"
              :key="image"
              :src="withBase(image)"
              :preview-src-list="previewImageList"
              fit="contain"
              class="preview-image"
            />
          </div>
          <el-empty v-else :description="previewMessage || text.noPreview" />
        </SectionCard>

        <SectionCard :title="text.deliverySection" style="margin-top: 16px">
          <div class="row-between">
            <div>
              <div class="title small-title">{{ text.deliveryTitle }}</div>
              <div class="hint">{{ text.deliveryDesc }}</div>
            </div>
            <div class="mini-actions">
              <el-button @click="loadDeliveries">{{ text.refreshDeliveries }}</el-button>
              <el-button type="primary" :disabled="!activeResume && !activeAttachment" @click="router.push('/student/resume-delivery')">{{ text.deliverResume }}</el-button>
            </div>
          </div>

          <div v-if="latestDeliveryAccount?.username" class="delivery-account-tip">
            <div class="block-title">{{ text.enterpriseAccountTitle }}</div>
            <p>
              {{ text.enterpriseAccountPrefix }}{{ latestDeliveryAccount.company_name }}
              {{ text.enterpriseAccountUser }}{{ latestDeliveryAccount.username }}
              {{ text.enterpriseAccountPassword }}
            </p>
          </div>

          <el-empty v-if="!deliveries.length" :description="text.emptyDeliveries" />
          <el-table v-else :data="deliveries">
            <el-table-column prop="company_name" :label="text.companyName" min-width="180" />
            <el-table-column prop="target_job_name" :label="text.targetJobColumn" min-width="180" />
            <el-table-column :label="text.matchScoreColumn" width="140">
              <template #default="{ row }">
                <el-tag :type="(row.match_score || 0) >= 70 ? 'success' : (row.match_score || 0) >= 40 ? 'warning' : 'info'">
                  {{ row.match_score || 0 }}%
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" :label="text.deliveryTimeColumn" min-width="180" />
            <el-table-column width="160" :label="text.action">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDeliveredResume(row)">{{ text.viewResume }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </SectionCard>
      </el-tab-pane>

      <el-tab-pane :label="text.experienceTab" name="experience">
        <div class="grid two">
          <SectionCard :title="text.projectSection">
            <el-table :data="projects">
              <el-table-column prop="name" :label="text.projectName" min-width="140" />
              <el-table-column prop="role" :label="text.role" width="120" />
              <el-table-column :label="text.techStack" min-width="180">
                <template #default="{ row }">{{ (row.technologies || []).join(' / ') }}</template>
              </el-table-column>
              <el-table-column width="140" :label="text.action">
                <template #default="{ row }">
                  <el-button link type="primary" @click="editProject(row)">{{ text.edit }}</el-button>
                  <el-button link type="danger" @click="removeResource('projects', row.id)">{{ text.remove }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="editor">
              <div class="block-title">{{ projectForm.id ? text.editProject : text.addProject }}</div>
              <el-input v-model="projectForm.name" :placeholder="text.projectName" />
              <el-input v-model="projectForm.role" :placeholder="text.rolePlaceholder" />
              <el-input v-model="projectForm.description" type="textarea" :rows="3" :placeholder="text.projectDesc" />
              <el-input v-model="projectTechText" :placeholder="text.techPlaceholder" />
              <el-input v-model="projectForm.outcome" type="textarea" :rows="2" :placeholder="text.projectOutcome" />
              <div class="mini-actions">
                <el-button @click="resetProjectForm">{{ text.reset }}</el-button>
                <el-button type="primary" @click="saveProject">{{ text.saveProject }}</el-button>
              </div>
            </div>
          </SectionCard>

          <SectionCard :title="text.internshipSection">
            <el-table :data="internships">
              <el-table-column prop="company" :label="text.company" min-width="140" />
              <el-table-column prop="position" :label="text.position" width="120" />
              <el-table-column :label="text.skills" min-width="180">
                <template #default="{ row }">{{ (row.skills || []).join(' / ') }}</template>
              </el-table-column>
              <el-table-column width="140" :label="text.action">
                <template #default="{ row }">
                  <el-button link type="primary" @click="editInternship(row)">{{ text.edit }}</el-button>
                  <el-button link type="danger" @click="removeResource('internships', row.id)">{{ text.remove }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="editor">
              <div class="block-title">{{ internshipForm.id ? text.editInternship : text.addInternship }}</div>
              <el-input v-model="internshipForm.company" :placeholder="text.company" />
              <el-input v-model="internshipForm.position" :placeholder="text.position" />
              <el-input v-model="internshipForm.description" type="textarea" :rows="3" :placeholder="text.internshipDesc" />
              <el-input v-model="internshipSkillText" :placeholder="text.skillPlaceholder" />
              <div class="mini-actions">
                <el-button @click="resetInternshipForm">{{ text.reset }}</el-button>
                <el-button type="primary" @click="saveInternship">{{ text.saveInternship }}</el-button>
              </div>
            </div>
          </SectionCard>
        </div>
      </el-tab-pane>

      <el-tab-pane :label="text.achievementTab" name="achievement">
        <div class="grid three">
          <SectionCard :title="text.certificateSection">
            <el-table :data="certificates">
              <el-table-column prop="name" :label="text.certificateName" min-width="120" />
              <el-table-column prop="issuer" :label="text.issuer" min-width="120" />
              <el-table-column width="120" :label="text.action">
                <template #default="{ row }">
                  <el-button link type="primary" @click="editCertificate(row)">{{ text.edit }}</el-button>
                  <el-button link type="danger" @click="removeResource('certificates', row.id)">{{ text.remove }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="editor">
              <el-input v-model="certificateForm.name" :placeholder="text.certificateName" />
              <el-input v-model="certificateForm.issuer" :placeholder="text.issuer" />
              <el-input v-model="certificateForm.description" type="textarea" :rows="2" :placeholder="text.desc" />
              <div class="mini-actions">
                <el-button @click="resetCertificateForm">{{ text.reset }}</el-button>
                <el-button type="primary" @click="saveCertificate">{{ text.save }}</el-button>
              </div>
            </div>
          </SectionCard>

          <SectionCard :title="text.competitionSection">
            <el-table :data="competitions">
              <el-table-column prop="name" :label="text.competitionName" min-width="120" />
              <el-table-column prop="award" :label="text.award" min-width="120" />
              <el-table-column width="120" :label="text.action">
                <template #default="{ row }">
                  <el-button link type="primary" @click="editCompetition(row)">{{ text.edit }}</el-button>
                  <el-button link type="danger" @click="removeResource('competitions', row.id)">{{ text.remove }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="editor">
              <el-input v-model="competitionForm.name" :placeholder="text.competitionName" />
              <el-input v-model="competitionForm.award" :placeholder="text.award" />
              <el-input v-model="competitionForm.level" :placeholder="text.level" />
              <el-input v-model="competitionForm.description" type="textarea" :rows="2" :placeholder="text.desc" />
              <div class="mini-actions">
                <el-button @click="resetCompetitionForm">{{ text.reset }}</el-button>
                <el-button type="primary" @click="saveCompetition">{{ text.save }}</el-button>
              </div>
            </div>
          </SectionCard>

          <SectionCard :title="text.campusSection">
            <el-table :data="campusExperiences">
              <el-table-column prop="title" :label="text.campusTitle" min-width="120" />
              <el-table-column prop="role" :label="text.role" min-width="120" />
              <el-table-column width="120" :label="text.action">
                <template #default="{ row }">
                  <el-button link type="primary" @click="editCampus(row)">{{ text.edit }}</el-button>
                  <el-button link type="danger" @click="removeResource('campus-experiences', row.id)">{{ text.remove }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="editor">
              <el-input v-model="campusForm.title" :placeholder="text.campusTitle" />
              <el-input v-model="campusForm.role" :placeholder="text.rolePlaceholder" />
              <el-input v-model="campusForm.duration" :placeholder="text.duration" />
              <el-input v-model="campusForm.description" type="textarea" :rows="2" :placeholder="text.desc" />
              <div class="mini-actions">
                <el-button @click="resetCampusForm">{{ text.reset }}</el-button>
                <el-button type="primary" @click="saveCampus">{{ text.save }}</el-button>
              </div>
            </div>
          </SectionCard>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="deliveryDialogVisible" :title="text.deliveryDialogTitle" width="960px">
      <div class="delivery-dialog-head">
        <div class="hint">{{ text.deliveryDialogDesc }}</div>
        <el-button @click="loadDeliveryTargets">{{ text.refreshDeliveries }}</el-button>
      </div>

      <el-empty v-if="!deliveryTargets.length" :description="text.emptyTargets" />
      <div v-else class="delivery-grid">
        <div v-for="company in deliveryTargets" :key="company.company_name" class="delivery-card">
          <div class="row-between">
            <div>
              <div class="block-title">{{ company.company_name }}</div>
              <div class="hint">{{ company.industry || text.noIndustry }} · {{ company.address || text.noAddress }}</div>
            </div>
            <div class="delivery-score">{{ company.match_score }}%</div>
          </div>

          <div class="tag-wrap">
            <el-tag round>{{ text.jobCount }}{{ company.job_count }}</el-tag>
            <el-tag round type="success">{{ company.company_type || text.noCompanyType }}</el-tag>
            <el-tag round type="warning">{{ company.company_size || text.noCompanySize }}</el-tag>
          </div>

          <p class="delivery-company-desc">{{ company.description || text.noCompanyDesc }}</p>

          <div class="delivery-opening-list">
            <div v-for="opening in company.openings" :key="opening.knowledge_doc_id" class="delivery-opening">
              <div>
                <div class="delivery-opening-name">{{ opening.job_name || text.unnamedJob }}</div>
                <div class="hint">{{ opening.job_category || text.noCategory }} · {{ opening.match_score }}%</div>
              </div>
              <el-button
                type="primary"
                size="small"
                :loading="deliveryLoadingDocId === opening.knowledge_doc_id"
                @click="deliverToOpening(company, opening)"
              >
                {{ text.deliverNow }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import { studentApi } from "@/api";
import { patchAssistantClientContext } from "@/composables/useAssistantSession";
import PageHeader from "@/components/PageHeader.vue";
import SectionCard from "@/components/SectionCard.vue";

const router = useRouter();
const fileBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const resumeTypes = ["pdf", "doc", "docx", "png", "jpg", "jpeg", "webp", "bmp"];
const text = {
  pageTitle: "简历管理",
  pageDesc: "统一管理简历、附件、版本和优化结果，支持图片/PDF/Word 上传、识别、回填与导出。",
  refresh: "\u5237\u65b0\u6570\u636e",
  backAssistant: "\u8fd4\u56de AI \u5bf9\u8bdd",
  resumeCount: "\u7b80\u5386\u7248\u672c\u6570",
  experienceCount: "\u9879\u76ee\u4e0e\u5b9e\u4e60\u7d20\u6750",
  achievementCount: "\u6210\u679c\u4e0e\u7ecf\u5386\u7d20\u6750",
  currentTarget: "\u5f53\u524d\u76ee\u6807\u65b9\u5411",
  pending: "\u5f85\u8bc6\u522b",
  resumeTab: "\u7b80\u5386\u8bc6\u522b\u4e0e\u4f18\u5316",
  experienceTab: "\u9879\u76ee\u4e0e\u5b9e\u4e60\u7d20\u6750",
  achievementTab: "\u8bc1\u4e66 / \u7ade\u8d5b / \u6821\u56ed\u7ecf\u5386",
  uploadSection: "\u4e0a\u4f20\u4e0e\u7248\u672c\u7ba1\u7406",
  resultSection: "\u8bc6\u522b\u7ed3\u679c\u4e0e\u753b\u50cf\u8054\u52a8",
  pickResume: "\u9009\u62e9\u56fe\u7247 / PDF / Word",
  currentFile: "\u5f53\u524d\u9009\u62e9\uff1a",
  noFile: "\u6682\u672a\u9009\u62e9\u6587\u4ef6",
  uploadDescPlaceholder: "\u4f8b\u5982\uff1a\u6821\u62db\u7248\u7b80\u5386 / \u6570\u636e\u5206\u6790\u65b9\u5411 / \u56fe\u7247\u7b80\u5386",
  upload: "\u4e0a\u4f20\u7b80\u5386",
  emptyResume: "\u5148\u4e0a\u4f20\u4e00\u4efd\u7b80\u5386\u5427",
  noDesc: "\u6682\u65e0\u8bf4\u660e",
  parse: "\u89e3\u6790",
  ingest: "\u8bc6\u522b\u5e76\u751f\u6210\u753b\u50cf",
  preview: "\u9884\u89c8",
  optimize: "AI \u4f18\u5316",
  remove: "\u5220\u9664",
  selectResumeFirst: "\u8bf7\u5148\u9009\u62e9\u4e00\u4efd\u7b80\u5386",
  parserEngine: "\u8bc6\u522b\u5f15\u64ce\uff1a",
  notParsed: "\u672a\u8bc6\u522b",
  parseResume: "\u89e3\u6790\u7b80\u5386",
  downloadWord: "\u4e0b\u8f7d Word",
  downloadPdf: "\u4e0b\u8f7d PDF",
  viewProfile: "\u67e5\u770b\u753b\u50cf\u9875",
  resumeScore: "\u7efc\u5408\u7b80\u5386\u5206",
  keywordScore: "\u5173\u952e\u8bcd\u5339\u914d",
  richnessScore: "\u5185\u5bb9\u4e30\u5bcc\u5ea6",
  projectScore: "\u9879\u76ee\u8bc1\u636e\u529b",
  ingestResultTitle: "\u8bc6\u522b\u56de\u586b\u4e0e\u753b\u50cf\u751f\u6210\u7ed3\u679c",
  ingestDone: "\u5df2\u5b8c\u6210\u201c\u7b80\u5386\u8bc6\u522b -> \u6863\u6848\u56de\u586b -> \u5b66\u751f\u753b\u50cf\u751f\u6210\u201d",
  updatedFields: "\u66f4\u65b0\u5b57\u6bb5\uff1a",
  newSkills: "\u65b0\u589e\u6280\u80fd\uff1a",
  newCerts: "\u65b0\u589e\u8bc1\u4e66\uff1a",
  newProjects: "\u65b0\u589e\u9879\u76ee\uff1a",
  newInternships: "\u65b0\u589e\u5b9e\u4e60\uff1a",
  none: "\u65e0",
  profileReady: "\u753b\u50cf\u5df2\u751f\u6210\uff0c\u53ef\u524d\u5f80\u753b\u50cf\u9875\u67e5\u770b\u3002",
  parseSummary: "\u89e3\u6790\u6458\u8981",
  noParsedContent: "\u8fd8\u6ca1\u6709\u89e3\u6790\u7ed3\u679c\uff0c\u5148\u70b9\u51fb\u201c\u89e3\u6790\u7b80\u5386\u201d\u6216\u201c\u8bc6\u522b\u5e76\u751f\u6210\u753b\u50cf\u201d\u3002",
  basicInfo: "\u8bc6\u522b\u51fa\u7684\u57fa\u7840\u4fe1\u606f",
  tagsTitle: "\u63d0\u53d6\u6807\u7b7e",
  skillTags: "\u6280\u80fd",
  interestTags: "\u5174\u8da3\u65b9\u5411",
  certificateTags: "\u8bc1\u4e66",
  optimizeSection: "AI \u4f18\u5316\u5efa\u8bae",
  clickOptimize: "\u70b9\u51fb AI \u4f18\u5316\u540e\u751f\u6210\u5185\u5bb9",
  optimizedSummary: "\u4f18\u5316\u540e\u7684\u804c\u4e1a\u6458\u8981",
  fullResumeSection: "\u4f18\u5316\u540e\u5b8c\u6574\u7b80\u5386",
  copyFullResume: "\u590d\u5236\u5b8c\u6574\u7b80\u5386",
  deepOptimizeOn: "\u5df2\u542f\u7528\u6df1\u5ea6\u4f18\u5316\uff08LLM + \u89c4\u5219\uff09",
  deepOptimizeFallback: "\u5df2\u5b8c\u6210\u89c4\u5219\u4e0e\u7ed3\u6784\u5316\u4f18\u5316",
  educationTitle: "\u6559\u80b2\u7ecf\u5386",
  keepHighlights: "\u5efa\u8bae\u4fdd\u7559\u7684\u4eae\u70b9",
  fixIssues: "\u4f18\u5148\u4fee\u6b63\u7684\u95ee\u9898",
  keywordTags: "\u5efa\u8bae\u8865\u5145\u7684\u5c97\u4f4d\u5173\u952e\u8bcd",
  previewSection: "\u7b80\u5386\u9884\u89c8",
  previewHint: "\u9009\u62e9\u4e00\u4efd\u56fe\u7247/PDF \u7b80\u5386\u540e\u5373\u53ef\u5c55\u793a\u9884\u89c8",
  noPreview: "\u5f53\u524d\u8fd8\u6ca1\u6709\u751f\u6210\u7b80\u5386\u9884\u89c8",
  deliverySection: "\u6295\u9012\u7b80\u5386",
  deliveryTitle: "\u6570\u636e\u5e93\u5c97\u4f4d\u753b\u50cf\u6295\u9012",
  deliveryDesc: "\u6295\u9012\u5165\u53e3\u5df2\u8fc1\u79fb\u5230\u72ec\u7acb\u9875\u9762\uff0c\u53ef\u5728\u5361\u7247\u4e2d\u67e5\u770b\u6240\u6709\u6570\u636e\u5e93\u5c97\u4f4d\u3001\u5c97\u4f4d\u753b\u50cf\u4e0e\u8def\u5f84\u56fe\u8c31\u3002",
  deliverResume: "\u524d\u5f80\u6295\u9012\u7b80\u5386",
  refreshDeliveries: "\u5237\u65b0\u6295\u9012",
  enterpriseAccountTitle: "\u4f01\u4e1a\u7aef\u8d26\u53f7\u5df2\u751f\u6210",
  enterpriseAccountPrefix: "\u5df2\u4e3a\u4f01\u4e1a\u81ea\u52a8\u521b\u5efa\u6295\u9012\u7bb1\u8d26\u53f7\uff1a",
  enterpriseAccountUser: "\uff0c\u767b\u5f55\u8d26\u53f7 ",
  enterpriseAccountPassword: "\uff0c\u9ed8\u8ba4\u5bc6\u7801 enterprise123",
  emptyDeliveries: "\u4f60\u8fd8\u6ca1\u6709\u6295\u9012\u7b80\u5386",
  companyName: "\u4f01\u4e1a\u540d\u79f0",
  targetJobColumn: "\u6295\u9012\u5c97\u4f4d",
  matchScoreColumn: "\u5339\u914d\u5ea6",
  deliveryTimeColumn: "\u6295\u9012\u65f6\u95f4",
  viewResume: "\u67e5\u770b\u7b80\u5386",
  deliveryDialogTitle: "\u9009\u62e9\u4f01\u4e1a\u5e76\u6295\u9012\u7b80\u5386",
  deliveryDialogDesc: "\u4ee5\u5f53\u524d\u9009\u4e2d\u7b80\u5386\u4e3a\u6295\u9012\u9644\u4ef6\uff0c\u4e0b\u65b9\u6309\u4f01\u4e1a\u5339\u914d\u5ea6\u6392\u5e8f\u5c55\u793a\u5168\u90e8\u4f01\u4e1a\u3002",
  emptyTargets: "\u6682\u672a\u8bfb\u53d6\u5230\u53ef\u6295\u9012\u7684\u4f01\u4e1a\u5217\u8868",
  noIndustry: "\u884c\u4e1a\u672a\u6807\u6ce8",
  noAddress: "\u5730\u70b9\u672a\u6807\u6ce8",
  noCompanyType: "\u4f01\u4e1a\u7c7b\u578b\u672a\u6807\u6ce8",
  noCompanySize: "\u4f01\u4e1a\u89c4\u6a21\u672a\u6807\u6ce8",
  noCompanyDesc: "\u6682\u65e0\u4f01\u4e1a\u4ecb\u7ecd",
  jobCount: "\u5c97\u4f4d\u6570\uff1a",
  unnamedJob: "\u672a\u547d\u540d\u5c97\u4f4d",
  noCategory: "\u5c97\u4f4d\u5206\u7c7b\u672a\u6807\u6ce8",
  deliverNow: "\u7acb\u5373\u6295\u9012",
  projectSection: "\u9879\u76ee\u7ecf\u5386",
  internshipSection: "\u5b9e\u4e60\u7ecf\u5386",
  certificateSection: "\u8bc1\u4e66",
  competitionSection: "\u7ade\u8d5b\u7ecf\u5386",
  campusSection: "\u6821\u56ed\u7ecf\u5386",
  projectName: "\u9879\u76ee\u540d\u79f0",
  competitionName: "\u7ade\u8d5b\u540d\u79f0",
  certificateName: "\u8bc1\u4e66\u540d\u79f0",
  campusTitle: "\u7ecf\u5386\u540d\u79f0",
  role: "\u89d2\u8272",
  rolePlaceholder: "\u62c5\u4efb\u89d2\u8272",
  techStack: "\u6280\u672f\u6808",
  skills: "\u6280\u80fd",
  company: "\u516c\u53f8",
  position: "\u5c97\u4f4d",
  issuer: "\u9881\u53d1\u673a\u6784",
  award: "\u83b7\u5956\u60c5\u51b5",
  level: "\u7ea7\u522b",
  duration: "\u6301\u7eed\u65f6\u957f",
  name: "\u59d3\u540d",
  phone: "\u624b\u673a\u53f7",
  email: "\u90ae\u7bb1",
  grade: "\u5e74\u7ea7",
  major: "\u4e13\u4e1a",
  college: "\u5b66\u9662",
  targetRole: "\u76ee\u6807\u5c97\u4f4d",
  targetIndustry: "\u76ee\u6807\u884c\u4e1a",
  projectDesc: "\u9879\u76ee\u63cf\u8ff0",
  projectOutcome: "\u9879\u76ee\u6210\u679c",
  internshipDesc: "\u7ecf\u5386\u63cf\u8ff0",
  techPlaceholder: "\u6280\u672f\u6808\uff0c\u9017\u53f7\u5206\u9694",
  skillPlaceholder: "\u6280\u80fd\uff0c\u9017\u53f7\u5206\u9694",
  desc: "\u8bf4\u660e",
  action: "\u64cd\u4f5c",
  edit: "\u7f16\u8f91",
  save: "\u4fdd\u5b58",
  reset: "\u91cd\u7f6e",
  addProject: "\u65b0\u589e\u9879\u76ee",
  editProject: "\u7f16\u8f91\u9879\u76ee",
  saveProject: "\u4fdd\u5b58\u9879\u76ee",
  addInternship: "\u65b0\u589e\u5b9e\u4e60",
  editInternship: "\u7f16\u8f91\u5b9e\u4e60",
  saveInternship: "\u4fdd\u5b58\u5b9e\u4e60",
};

const activeTab = ref("resume");
const uploadFile = ref(null);
const uploadDescription = ref("");
const uploadCreateResume = ref(true);
const attachments = ref([]);
const activeAttachmentId = ref(null);
const resumes = ref([]);
const activeResumeId = ref(null);
const resumeVersionsByResumeId = ref({});
const activeResumeVersionId = ref(null);
const parsedResume = ref(null);
const optimization = ref(null);
const ingestResult = ref(null);
const previewImages = ref([]);
const previewMessage = ref("");
const uploading = ref(false);
const parsing = ref(false);
const optimizing = ref(false);
const ingesting = ref(false);
const deliveryDialogVisible = ref(false);
const deliveryTargets = ref([]);
const deliveries = ref([]);
const deliveryLoadingDocId = ref("");
const latestDeliveryAccount = ref(null);

const projects = ref([]);
const internships = ref([]);
const certificates = ref([]);
const competitions = ref([]);
const campusExperiences = ref([]);

const projectForm = reactive({ id: null, name: "", role: "", description: "", technologies: [], outcome: "", relevance_score: 80 });
const internshipForm = reactive({ id: null, company: "", position: "", description: "", skills: [], relevance_score: 80 });
const certificateForm = reactive({ id: null, name: "", issuer: "", description: "" });
const competitionForm = reactive({ id: null, name: "", award: "", level: "", description: "" });
const campusForm = reactive({ id: null, title: "", role: "", duration: "", description: "" });

const projectTechText = computed({
  get: () => (projectForm.technologies || []).join(", "),
  set: (value) => (projectForm.technologies = value.split(",").map((item) => item.trim()).filter(Boolean)),
});

const internshipSkillText = computed({
  get: () => (internshipForm.skills || []).join(", "),
  set: (value) => (internshipForm.skills = value.split(",").map((item) => item.trim()).filter(Boolean)),
});

const resumeAttachments = computed(() => attachments.value.filter((item) => resumeTypes.includes((item.file_type || "").toLowerCase())).sort((a, b) => b.id - a.id));
const activeAttachment = computed(() => resumeAttachments.value.find((item) => item.id === activeAttachmentId.value) || resumeAttachments.value[0] || null);
const activeResume = computed(() => resumes.value.find((item) => item.id === activeResumeId.value) || resumes.value[0] || null);
const activeResumeVersions = computed(() => {
  if (!activeResume.value) return [];
  return resumeVersionsByResumeId.value[activeResume.value.id] || [];
});
const activeResumeVersion = computed(
  () => activeResumeVersions.value.find((item) => item.id === activeResumeVersionId.value) || activeResumeVersions.value[0] || null,
);
const parsedSkills = computed(() => parsedResume.value?.skills || optimization.value?.parsed_resume?.skills || ingestResult.value?.parsed_resume?.skills || []);
const parsedInterests = computed(() => parsedResume.value?.interests || ingestResult.value?.parsed_resume?.interests || []);
const parsedCertificates = computed(() => parsedResume.value?.certificates || ingestResult.value?.parsed_resume?.certificates || []);
const previewImageList = computed(() => previewImages.value.map((item) => withBase(item)));
const optimizedResumeDocument = computed(() => optimization.value?.optimized_resume_document || null);
const optimizedResumeMarkdown = computed(() => String(optimization.value?.optimized_resume_markdown || ""));
const ingestSummary = computed(() => {
  const result = ingestResult.value || {};
  const sync = result.sync_summary || {};
  const counts = result.merged_counts || {};
  return {
    updatedFields: result.updated_fields || sync.updated_fields || [],
    skillsAdded: Number(sync.skills_added ?? counts.skills ?? 0),
    certificatesAdded: Number(sync.certificates_added ?? counts.certificates ?? 0),
    projectsAdded: Number(sync.projects_added ?? counts.projects ?? 0),
    internshipsAdded: Number(sync.internships_added ?? counts.internships ?? 0),
  };
});

const withBase = (url) => {
  if (!url) return "";
  if (String(url).startsWith("http://") || String(url).startsWith("https://")) return url;
  return `${fileBase}${url}`;
};

const normalizePreviewImages = (value) => {
  const rows = Array.isArray(value) ? value : [];
  return rows
    .map((item) => {
      if (!item) return "";
      if (typeof item === "string") return item;
      if (typeof item === "object") return item.url || "";
      return "";
    })
    .filter(Boolean);
};

const joinNonEmpty = (values, sep = " - ") => values.filter((item) => String(item || "").trim()).join(sep);

const formatProjectTitle = (item = {}) =>
  joinNonEmpty([item.name, joinNonEmpty([item.role, item.duration], " | ")]);

const formatInternshipTitle = (item = {}) =>
  joinNonEmpty([item.company, joinNonEmpty([item.position, item.duration], " | ")]);

const formatCompetitionTitle = (item = {}) =>
  joinNonEmpty([item.name, joinNonEmpty([item.award, item.level], " | ")]);

const formatCampusTitle = (item = {}) =>
  joinNonEmpty([item.title, joinNonEmpty([item.role, item.duration], " | ")]);

const buildMarkdownFromResumeDocument = (doc) => {
  if (!doc || typeof doc !== "object") return "";
  const lines = [];
  const title = doc.title || "优化简历";
  const name = doc.name || "";
  lines.push(name ? `# ${name} - ${title}` : `# ${title}`);
  lines.push("");
  if (doc.target_role) lines.push(`- 目标岗位：${doc.target_role}`);
  if (doc.phone) lines.push(`- 电话：${doc.phone}`);
  if (doc.email) lines.push(`- 邮箱：${doc.email}`);
  if (doc.github) lines.push(`- GitHub：${doc.github}`);
  if (doc.college) lines.push(`- 学校：${doc.college}`);
  if (doc.major) lines.push(`- 专业：${doc.major}`);
  if (doc.grade) lines.push(`- 年级：${doc.grade}`);
  if (doc.target_city) lines.push(`- 目标城市：${doc.target_city}`);

  if (doc.summary) lines.push("", "## 个人简介", doc.summary);
  if (doc.education_experience) lines.push("", "## 教育经历", doc.education_experience);
  if (Array.isArray(doc.skills) && doc.skills.length) lines.push("", "## 核心技能", doc.skills.join("、"));
  if (Array.isArray(doc.certificates) && doc.certificates.length) {
    lines.push("", "## 证书");
    doc.certificates.forEach((item) => lines.push(`- ${item}`));
  }
  if (Array.isArray(doc.projects) && doc.projects.length) {
    lines.push("", "## 项目经历");
    doc.projects.forEach((item) => {
      const titleLine = formatProjectTitle(item);
      if (titleLine) lines.push(`- ${titleLine}`);
      if (item.rewrite) lines.push(`  - ${item.rewrite}`);
    });
  }
  if (Array.isArray(doc.internships) && doc.internships.length) {
    lines.push("", "## 实习经历");
    doc.internships.forEach((item) => {
      const titleLine = formatInternshipTitle(item);
      if (titleLine) lines.push(`- ${titleLine}`);
      if (item.rewrite) lines.push(`  - ${item.rewrite}`);
    });
  }
  if (Array.isArray(doc.competitions) && doc.competitions.length) {
    lines.push("", "## 竞赛经历");
    doc.competitions.forEach((item) => {
      const titleLine = formatCompetitionTitle(item);
      if (titleLine) lines.push(`- ${titleLine}`);
      if (item.description) lines.push(`  - ${item.description}`);
    });
  }
  if (Array.isArray(doc.campus_experiences) && doc.campus_experiences.length) {
    lines.push("", "## 校园经历");
    doc.campus_experiences.forEach((item) => {
      const titleLine = formatCampusTitle(item);
      if (titleLine) lines.push(`- ${titleLine}`);
      if (item.description) lines.push(`  - ${item.description}`);
    });
  }
  return lines.join("\n").trim();
};

const copyOptimizedResume = async () => {
  const markdown = optimizedResumeMarkdown.value || buildMarkdownFromResumeDocument(optimizedResumeDocument.value);
  if (!markdown) {
    ElMessage.warning(text.clickOptimize);
    return;
  }
  try {
    await navigator.clipboard.writeText(markdown);
    ElMessage.success("copied");
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = markdown;
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    ElMessage.success("copied");
  }
};

const resetProjectForm = () => Object.assign(projectForm, { id: null, name: "", role: "", description: "", technologies: [], outcome: "", relevance_score: 80 });
const resetInternshipForm = () => Object.assign(internshipForm, { id: null, company: "", position: "", description: "", skills: [], relevance_score: 80 });
const resetCertificateForm = () => Object.assign(certificateForm, { id: null, name: "", issuer: "", description: "" });
const resetCompetitionForm = () => Object.assign(competitionForm, { id: null, name: "", award: "", level: "", description: "" });
const resetCampusForm = () => Object.assign(campusForm, { id: null, title: "", role: "", duration: "", description: "" });

const syncActiveAttachment = () => {
  if (!resumeAttachments.value.length) {
    activeAttachmentId.value = null;
    parsedResume.value = null;
    optimization.value = null;
    ingestResult.value = null;
    previewImages.value = [];
    previewMessage.value = "";
    return;
  }
  if (!resumeAttachments.value.some((item) => item.id === activeAttachmentId.value)) {
    activeAttachmentId.value = resumeAttachments.value[0].id;
  }
};

const syncAssistantContext = () => {
  const versionAttachment = activeResumeVersion.value?.attachment || null;
  const sourceAttachment = activeResume.value?.source_attachment || null;
  const attachment = versionAttachment || activeAttachment.value || sourceAttachment || null;
  const attachmentId =
    activeResumeVersion.value?.attachment_id || attachment?.id || activeResume.value?.source_attachment_id || null;
  patchAssistantClientContext({
    resume_id: activeResume.value?.id || null,
    resume_version_id: activeResumeVersionId.value || activeResume.value?.current_version_id || null,
    attachment_id: attachmentId,
    attachment: attachmentId
      ? {
          id: attachmentId,
          file_name: attachment?.file_name || "",
          file_type: attachment?.file_type || "",
        }
      : {},
    target_job: activeResume.value?.target_job || parsedResume.value?.target_role || optimization.value?.target_role || "",
    target_city: activeResume.value?.target_city || "",
    target_industry: activeResume.value?.target_industry || "",
  });
};

const syncActiveResume = () => {
  if (!resumes.value.length) {
    activeResumeId.value = null;
    activeResumeVersionId.value = null;
    syncAssistantContext();
    return;
  }
  if (!resumes.value.some((item) => item.id === activeResumeId.value)) {
    activeResumeId.value = resumes.value[0].id;
  }
  const current = resumes.value.find((item) => item.id === activeResumeId.value);
  if (current) {
    activeResumeVersionId.value = current.current_version_id || null;
  }
  syncAssistantContext();
};

const loadResumeVersions = async (resumeId) => {
  if (!resumeId) return [];
  const res = await studentApi.listResumeVersions(resumeId);
  const items = res.data || [];
  resumeVersionsByResumeId.value = { ...resumeVersionsByResumeId.value, [resumeId]: items };
  if (resumeId === activeResumeId.value) {
    if (!items.some((item) => item.id === activeResumeVersionId.value)) {
      activeResumeVersionId.value = items[0]?.id || null;
    }
  }
  return items;
};

const loadResumes = async () => {
  const res = await studentApi.listResumes();
  resumes.value = res.data || [];
  syncActiveResume();
  if (activeResume.value?.id) {
    await loadResumeVersions(activeResume.value.id);
    const selectedVersion =
      activeResumeVersions.value.find((item) => item.id === activeResumeVersionId.value) || activeResumeVersions.value[0] || null;
    if (selectedVersion?.attachment_id) {
      activeAttachmentId.value = selectedVersion.attachment_id;
    }
  }
};

const selectResume = async (item) => {
  activeResumeId.value = item.id;
  activeResumeVersionId.value = item.current_version_id || null;
  await loadResumeVersions(item.id);
  const selectedVersion =
    activeResumeVersions.value.find((version) => version.id === activeResumeVersionId.value) || activeResumeVersions.value[0] || null;
  if (selectedVersion?.attachment_id) {
    activeAttachmentId.value = selectedVersion.attachment_id;
  }
  syncAssistantContext();
};

const selectResumeVersion = (version) => {
  activeResumeVersionId.value = version.id;
  if (version.attachment_id) {
    activeAttachmentId.value = version.attachment_id;
  }
  syncAssistantContext();
};

const loadAttachments = async () => {
  const res = await studentApi.listAttachments();
  attachments.value = res.data || [];
  syncActiveAttachment();
};

const loadExperienceData = async () => {
  const [projectRes, internshipRes, certificateRes, competitionRes, campusRes] = await Promise.all([
    studentApi.listResource("projects"),
    studentApi.listResource("internships"),
    studentApi.listResource("certificates"),
    studentApi.listResource("competitions"),
    studentApi.listResource("campus-experiences"),
  ]);
  projects.value = projectRes.data || [];
  internships.value = internshipRes.data || [];
  certificates.value = certificateRes.data || [];
  competitions.value = competitionRes.data || [];
  campusExperiences.value = campusRes.data || [];
};

const loadDeliveryTargets = async () => {
  const res = await studentApi.listResumeDeliveryTargets();
  deliveryTargets.value = res.data?.items || [];
};

const loadDeliveries = async () => {
  const res = await studentApi.listResumeDeliveries();
  deliveries.value = res.data || [];
};

const loadAll = async () => Promise.all([loadAttachments(), loadResumes(), loadExperienceData(), loadDeliveries()]);

const handleChange = (file) => {
  uploadFile.value = file.raw;
  if (!uploadDescription.value) uploadDescription.value = `${file.name} - resume`;
};

const selectAttachment = (item) => {
  activeAttachmentId.value = item.id;
  parsedResume.value = null;
  optimization.value = null;
  ingestResult.value = null;
  previewImages.value = [];
  previewMessage.value = "";
};

const openCreateResumePrompt = async () => {
  try {
    const { value } = await ElMessageBox.prompt("请输入简历名称", "新建简历", {
      inputPlaceholder: "例如：产品经理校招版",
      confirmButtonText: "创建",
      cancelButtonText: "取消",
    });
    if (!value) return;
    await studentApi.createResume({ title: value, source_attachment_id: activeAttachment.value?.id || null });
    await loadResumes();
    ElMessage.success("resume created");
  } catch (_) {}
};

const openEditResumePrompt = async () => {
  if (!activeResume.value) return;
  try {
    const { value } = await ElMessageBox.prompt("修改简历名称", "编辑简历", {
      inputValue: activeResume.value.title || "",
      confirmButtonText: "保存",
      cancelButtonText: "取消",
    });
    if (!value) return;
    await studentApi.updateResume(activeResume.value.id, { title: value });
    await loadResumes();
    ElMessage.success("resume updated");
  } catch (_) {}
};

const createResumeFromSelectedAttachment = async () => {
  if (!activeAttachment.value) {
    ElMessage.warning(text.selectResumeFirst);
    return;
  }
  const res = await studentApi.createResumeFromAttachment(activeAttachment.value.id, {
    title: activeAttachment.value.file_name.replace(/\.(pdf|doc|docx|png|jpg|jpeg|webp|bmp)$/i, ""),
  });
  await loadResumes();
  activeResumeId.value = res.data?.id || activeResumeId.value;
  ElMessage.success("resume created from attachment");
};

const createVersionFromCurrentAttachment = async () => {
  if (!activeResume.value || !activeAttachment.value) return;
  await studentApi.createResumeVersion(activeResume.value.id, {
    attachment_id: activeAttachment.value.id,
    change_summary: "从当前附件创建版本",
  });
  await loadResumes();
  await loadResumeVersions(activeResume.value.id);
  ElMessage.success("new version saved");
};

const cloneActiveResume = async () => {
  if (!activeResume.value) return;
  await studentApi.cloneResume(activeResume.value.id, { title: `${activeResume.value.title}-副本` });
  await loadResumes();
  ElMessage.success("resume cloned");
};

const setActiveResumeDefault = async () => {
  if (!activeResume.value) return;
  await studentApi.setDefaultResume(activeResume.value.id);
  await loadResumes();
  ElMessage.success("default resume updated");
};

const deleteActiveResume = async () => {
  if (!activeResume.value) return;
  await ElMessageBox.confirm(`delete resume ${activeResume.value.title}?`, "confirm", { type: "warning" });
  await studentApi.deleteResume(activeResume.value.id);
  await loadResumes();
  ElMessage.success("resume deleted");
};

const optimizeActiveResume = async () => {
  if (!activeResume.value) {
    ElMessage.warning("please select resume");
    return;
  }
  optimizing.value = true;
  try {
    const res = await studentApi.optimizeResumeByResume(activeResume.value.id, {
      resume_version_id: activeResumeVersionId.value || activeResume.value.current_version_id,
      change_summary: "AI 优化生成",
      target_role: activeResume.value.target_job || parsedResume.value?.target_role || "",
    });
    optimization.value = res.data?.optimization || null;
    parsedResume.value = res.data?.optimization?.parsed_resume || parsedResume.value;
    previewImages.value = normalizePreviewImages(res.data?.optimization?.preview_images || res.data?.optimization?.images || []);
    previewMessage.value = res.data?.optimization?.preview_message || "";
    await loadResumes();
    if (activeResume.value?.id) await loadResumeVersions(activeResume.value.id);
    ElMessage.success("optimized as new version");
  } finally {
    optimizing.value = false;
  }
};

const openDeliveryDialog = async () => {
  if (!activeAttachment.value && !activeResume.value) {
    ElMessage.warning(text.selectResumeFirst);
    return;
  }
  deliveryDialogVisible.value = true;
  if (!deliveryTargets.value.length) {
    await loadDeliveryTargets();
  }
};

const uploadResume = async () => {
  if (!uploadFile.value) return;
  uploading.value = true;
  try {
    const formData = new FormData();
    formData.append("file", uploadFile.value);
    formData.append("description", uploadDescription.value);
    const res = await studentApi.uploadAttachment(formData);
    ElMessage.success("resume uploaded");
    if (uploadCreateResume.value && res.data?.id) {
      await studentApi.createResumeFromAttachment(res.data.id, {
        title: (res.data.file_name || uploadFile.value.name || "").replace(/\.(pdf|doc|docx|png|jpg|jpeg|webp|bmp)$/i, ""),
      });
    }
    uploadFile.value = null;
    uploadDescription.value = "";
    await loadAttachments();
    await loadResumes();
    if (res.data?.id) activeAttachmentId.value = res.data.id;
  } finally {
    uploading.value = false;
  }
};

const parseAttachment = async (item) => {
  const attachment = item || activeAttachment.value;
  if (!attachment) return;
  parsing.value = true;
  activeAttachmentId.value = attachment.id;
  try {
    const res = await studentApi.parseResume(attachment.id);
    parsedResume.value = res.data;
    ingestResult.value = null;
    await loadResumes();
    ElMessage.success("resume parsed");
  } finally {
    parsing.value = false;
  }
};

const ingestAttachment = async (item) => {
  const attachment = item || activeAttachment.value;
  if (!attachment) return;
  ingesting.value = true;
  activeAttachmentId.value = attachment.id;
  try {
    const res = await studentApi.ingestResume(attachment.id);
    ingestResult.value = res.data;
    parsedResume.value = res.data.parsed_resume || parsedResume.value;
    await loadExperienceData();
    await loadDeliveryTargets();
    await loadResumes();
    ElMessage.success("profile generated");
  } finally {
    ingesting.value = false;
  }
};

const ensureResumeForAttachment = async (attachment, parsed = {}) => {
  await loadResumes();
  let resume = resumes.value.find((item) => Number(item.source_attachment_id) === Number(attachment.id));
  if (!resume) {
    const res = await studentApi.createResumeFromAttachment(attachment.id, {
      title: String(attachment.file_name || "简历").replace(/\.(pdf|doc|docx|png|jpg|jpeg|webp|bmp)$/i, ""),
      target_job: parsed.target_role || "",
      target_industry: parsed.target_industry || "",
      target_city: parsed.target_city || "",
      summary: parsed.summary || "",
    });
    resume = res.data;
  }
  activeResumeId.value = resume.id;
  activeAttachmentId.value = attachment.id;
  await loadResumes();
  resume = resumes.value.find((item) => item.id === activeResumeId.value) || resume;
  await loadResumeVersions(resume.id);
  return resume;
};

const optimizeAttachment = async (item) => {
  const attachment = item || activeAttachment.value;
  if (!attachment) return;
  optimizing.value = true;
  activeAttachmentId.value = attachment.id;
  try {
    const parseRes = await studentApi.parseResume(attachment.id);
    parsedResume.value = parseRes.data;
    const ingestRes = await studentApi.ingestResume(attachment.id);
    ingestResult.value = ingestRes.data;
    parsedResume.value = ingestRes.data?.parsed_resume || parsedResume.value;
    await loadExperienceData();
    await loadDeliveryTargets();

    const resume = await ensureResumeForAttachment(attachment, parsedResume.value || {});
    const res = await studentApi.optimizeResumeByResume(resume.id, {
      resume_version_id: activeResumeVersionId.value || resume.current_version_id,
      change_summary: "AI 优化生成",
      target_role: parsedResume.value?.target_role || resume.target_job || "",
    });
    optimization.value = res.data?.optimization || null;
    previewImages.value = normalizePreviewImages(res.data?.optimization?.preview_images || res.data?.optimization?.images || []);
    previewMessage.value = res.data?.optimization?.preview_message || "";
    parsedResume.value = res.data?.optimization?.parsed_resume || parsedResume.value;
    await loadResumes();
    if (activeResumeId.value) await loadResumeVersions(activeResumeId.value);
    ElMessage.success("resume optimized and saved");
  } finally {
    optimizing.value = false;
  }
};

const previewAttachment = async (item) => {
  const attachment = item || activeAttachment.value;
  if (!attachment) return;
  activeAttachmentId.value = attachment.id;
  const res = await studentApi.previewResumePdf(attachment.id);
  previewImages.value = normalizePreviewImages(res.data?.preview_images || res.data?.images || []);
  previewMessage.value = res.data.message || "";
  if (res.data?.supported) ElMessage.success("preview loaded");
  else if (previewMessage.value) ElMessage.warning(previewMessage.value);
};

const downloadCurrentWord = async () => {
  const attachmentId = activeResumeVersion.value?.attachment_id || activeAttachment.value?.id;
  if (!attachmentId) {
    ElMessage.warning(text.selectResumeFirst);
    return;
  }
  try {
    const blob = await studentApi.downloadResumeWord(attachmentId, {
      resumeId: activeResume.value?.id || null,
      resumeVersionId: activeResumeVersionId.value || null,
      targetRole: optimization.value?.target_role || activeResume.value?.target_job || "",
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const baseName = activeResume.value?.title || activeAttachment.value?.file_name || "resume";
    link.download = `${String(baseName).replace(/\.(pdf|doc|docx|png|jpg|jpeg|webp|bmp)$/i, "") || "resume"}-optimized.docx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    ElMessage.success("word downloaded");
  } catch (error) {
    ElMessage.error(error.message || "word download failed");
  }
};

const downloadCurrentPdf = async () => {
  const attachmentId = activeResumeVersion.value?.attachment_id || activeAttachment.value?.id;
  if (!attachmentId) {
    ElMessage.warning(text.selectResumeFirst);
    return;
  }
  try {
    const blob = await studentApi.downloadResumePdf(attachmentId, {
      resumeId: activeResume.value?.id || null,
      resumeVersionId: activeResumeVersionId.value || null,
      targetRole: optimization.value?.target_role || activeResume.value?.target_job || "",
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const baseName = activeResume.value?.title || activeAttachment.value?.file_name || "resume";
    link.download = `${String(baseName).replace(/\.(pdf|doc|docx|png|jpg|jpeg|webp|bmp)$/i, "") || "resume"}-optimized.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    ElMessage.success("pdf downloaded");
  } catch (error) {
    ElMessage.error(error.message || "pdf download failed");
  }
};

const deliverToOpening = async (company, opening) => {
  if (!activeAttachment.value && !activeResume.value) {
    ElMessage.warning(text.selectResumeFirst);
    return;
  }
  deliveryLoadingDocId.value = opening.knowledge_doc_id;
  try {
    const payload = {
      knowledge_doc_id: opening.knowledge_doc_id,
      company_name: company.company_name,
      target_job_name: opening.job_name,
      target_job_category: opening.job_category,
      resume_version_id: activeResumeVersionId.value || activeResume.value?.current_version_id || null,
    };
    const res = activeResume.value
      ? await studentApi.deliverResumeByResume(activeResume.value.id, payload)
      : await studentApi.deliverResume({ attachment_id: activeAttachment.value.id, ...payload });
    latestDeliveryAccount.value = res.data?.enterprise_account || null;
    await loadDeliveries();
    ElMessage.success("resume delivered");
  } finally {
    deliveryLoadingDocId.value = "";
  }
};

const openDeliveredResume = (row) => {
  if (!row?.attachment?.file_path) {
    ElMessage.warning(text.noPreview);
    return;
  }
  window.open(withBase(row.attachment.file_path), "_blank");
};

const removeAttachment = async (item) => {
  await ElMessageBox.confirm(`delete resume ${item.file_name}?`, "confirm", { type: "warning" });
  await studentApi.deleteAttachment(item.id);
  ElMessage.success("resume removed");
  if (item.id === activeAttachmentId.value) activeAttachmentId.value = null;
  await loadAttachments();
};

const saveProject = async () => {
  if (projectForm.id) await studentApi.updateResource("projects", projectForm.id, projectForm);
  else await studentApi.createResource("projects", projectForm);
  resetProjectForm();
  await loadExperienceData();
  ElMessage.success("project saved");
};

const saveInternship = async () => {
  if (internshipForm.id) await studentApi.updateResource("internships", internshipForm.id, internshipForm);
  else await studentApi.createResource("internships", internshipForm);
  resetInternshipForm();
  await loadExperienceData();
  ElMessage.success("internship saved");
};

const saveCertificate = async () => {
  if (certificateForm.id) await studentApi.updateResource("certificates", certificateForm.id, certificateForm);
  else await studentApi.createResource("certificates", certificateForm);
  resetCertificateForm();
  await loadExperienceData();
  ElMessage.success("certificate saved");
};

const saveCompetition = async () => {
  if (competitionForm.id) await studentApi.updateResource("competitions", competitionForm.id, competitionForm);
  else await studentApi.createResource("competitions", competitionForm);
  resetCompetitionForm();
  await loadExperienceData();
  ElMessage.success("competition saved");
};

const saveCampus = async () => {
  if (campusForm.id) await studentApi.updateResource("campus-experiences", campusForm.id, campusForm);
  else await studentApi.createResource("campus-experiences", campusForm);
  resetCampusForm();
  await loadExperienceData();
  ElMessage.success("campus record saved");
};

const removeResource = async (resource, id) => {
  await studentApi.deleteResource(resource, id);
  ElMessage.success("removed");
  await loadExperienceData();
};

const editProject = (row) => Object.assign(projectForm, JSON.parse(JSON.stringify(row)));
const editInternship = (row) => Object.assign(internshipForm, JSON.parse(JSON.stringify(row)));
const editCertificate = (row) => Object.assign(certificateForm, JSON.parse(JSON.stringify(row)));
const editCompetition = (row) => Object.assign(competitionForm, JSON.parse(JSON.stringify(row)));
const editCampus = (row) => Object.assign(campusForm, JSON.parse(JSON.stringify(row)));

onMounted(loadAll);
</script>

<style scoped>
.page-shell {
  --surface-text-primary: #0f172a;
  --surface-text-secondary: #475569;
  --surface-text-muted: #64748b;
  --surface-title-color: #334155;
  --surface-card-bg: linear-gradient(180deg, #ffffff, #f8fbff);
  --surface-card-border: #e4ebf4;
  --surface-card-highlight-bg: linear-gradient(135deg, #eff6ff, #eef2ff);
  --surface-card-highlight-border: #bfdbfe;
  --surface-panel-bg: #fbfdff;
  --surface-panel-border: #e4ebf4;
  --surface-subtle-bg: #f8fafc;
  --surface-subtle-border: #e2e8f0;
  --accent-panel-bg: #eff6ff;
  --accent-panel-border: #bfdbfe;
  --accent-panel-strong: #2563eb;
  --editor-divider: #edf2f7;
  --preview-panel-bg: #f8fafc;
}

:global(.role-student) .page-shell {
  --surface-text-primary: #efffff;
  --surface-text-secondary: rgba(228, 243, 248, 0.9);
  --surface-text-muted: rgba(210, 232, 239, 0.82);
  --surface-title-color: #efffff;
  --surface-card-bg: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(28, 37, 65, 0.92));
  --surface-card-border: rgba(111, 255, 233, 0.14);
  --surface-card-highlight-bg: linear-gradient(135deg, rgba(58, 80, 107, 0.92), rgba(91, 192, 190, 0.18));
  --surface-card-highlight-border: rgba(111, 255, 233, 0.18);
  --surface-panel-bg: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(28, 37, 65, 0.88));
  --surface-panel-border: rgba(111, 255, 233, 0.14);
  --surface-subtle-bg: rgba(11, 19, 43, 0.72);
  --surface-subtle-border: rgba(111, 255, 233, 0.12);
  --accent-panel-bg: linear-gradient(135deg, rgba(15, 98, 254, 0.24), rgba(91, 192, 190, 0.16));
  --accent-panel-border: rgba(111, 255, 233, 0.18);
  --accent-panel-strong: #efffff;
  --editor-divider: rgba(111, 255, 233, 0.12);
  --preview-panel-bg: rgba(11, 19, 43, 0.72);
}

:global(.role-admin) .page-shell {
  --surface-text-primary: #eff6ff;
  --surface-text-secondary: rgba(219, 234, 254, 0.88);
  --surface-text-muted: rgba(191, 219, 254, 0.82);
  --surface-title-color: #eff6ff;
  --surface-card-bg: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.92));
  --surface-card-border: rgba(56, 189, 248, 0.14);
  --surface-card-highlight-bg: linear-gradient(135deg, rgba(51, 65, 85, 0.94), rgba(56, 189, 248, 0.18));
  --surface-card-highlight-border: rgba(56, 189, 248, 0.18);
  --surface-panel-bg: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.88));
  --surface-panel-border: rgba(56, 189, 248, 0.14);
  --surface-subtle-bg: rgba(15, 23, 42, 0.74);
  --surface-subtle-border: rgba(56, 189, 248, 0.12);
  --accent-panel-bg: linear-gradient(135deg, rgba(15, 98, 254, 0.24), rgba(56, 189, 248, 0.18));
  --accent-panel-border: rgba(56, 189, 248, 0.18);
  --accent-panel-strong: #eff6ff;
  --editor-divider: rgba(56, 189, 248, 0.12);
  --preview-panel-bg: rgba(15, 23, 42, 0.74);
}

:global(.role-enterprise) .page-shell {
  --surface-text-primary: #f8fffd;
  --surface-text-secondary: rgba(236, 247, 242, 0.9);
  --surface-text-muted: rgba(226, 240, 233, 0.84);
  --surface-title-color: #ffffff;
  --surface-card-bg: linear-gradient(180deg, rgba(12, 25, 50, 0.96), rgba(18, 38, 70, 0.92));
  --surface-card-border: rgba(111, 255, 233, 0.16);
  --surface-card-highlight-bg: linear-gradient(135deg, rgba(20, 55, 89, 0.94), rgba(111, 255, 233, 0.18));
  --surface-card-highlight-border: rgba(111, 255, 233, 0.18);
  --surface-panel-bg: linear-gradient(180deg, rgba(10, 21, 44, 0.94), rgba(15, 31, 58, 0.9));
  --surface-panel-border: rgba(111, 255, 233, 0.16);
  --surface-subtle-bg: rgba(10, 21, 44, 0.76);
  --surface-subtle-border: rgba(111, 255, 233, 0.12);
  --accent-panel-bg: linear-gradient(135deg, rgba(29, 78, 216, 0.28), rgba(111, 255, 233, 0.16));
  --accent-panel-border: rgba(111, 255, 233, 0.18);
  --accent-panel-strong: #ffffff;
  --editor-divider: rgba(111, 255, 233, 0.12);
  --preview-panel-bg: rgba(10, 21, 44, 0.76);
}

.stat-grid,
.grid {
  display: grid;
  gap: 16px;
}

.stat-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 18px 0;
}

.grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.grid.three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.resume-manager {
  margin-bottom: 16px;
  align-items: start;
}

.version-list {
  margin-top: 8px;
}

.fit-grid {
  align-items: start;
}

.stat-card {
  padding: 18px;
  border-radius: 22px;
  background: var(--surface-card-bg);
  border: 1px solid var(--surface-card-border);
}

.stat-card.highlight {
  background: var(--surface-card-highlight-bg);
  border-color: var(--surface-card-highlight-border);
}

.stat-label,
.hint {
  font-size: 13px;
  color: var(--surface-text-muted);
}

.stat-value {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  color: var(--surface-text-primary);
}

.stat-value.small {
  font-size: 22px;
}

.tabs {
  margin-top: 6px;
}

.tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.tabs :deep(.el-tabs__nav-wrap) {
  padding: 6px;
  border-radius: 18px;
}

.tabs :deep(.el-tabs__nav-wrap::after),
.tabs :deep(.el-tabs__active-bar) {
  display: none;
}

.tabs :deep(.el-tabs__nav) {
  gap: 8px;
}

.tabs :deep(.el-tabs__item) {
  height: 46px;
  padding: 0 18px;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.2s ease;
}

:global(.role-student) .tabs :deep(.el-tabs__nav-wrap) {
  background: linear-gradient(180deg, rgba(11, 19, 43, 0.82), rgba(28, 37, 65, 0.9));
  border: 1px solid rgba(91, 192, 190, 0.14);
  box-shadow: inset 0 1px 0 rgba(111, 255, 233, 0.04);
}

:global(.role-student) .tabs :deep(.el-tabs__item) {
  color: rgba(214, 247, 244, 0.58);
}

:global(.role-student) .tabs :deep(.el-tabs__item:hover) {
  color: #dcfff8;
  background: rgba(91, 192, 190, 0.08);
}

:global(.role-student) .tabs :deep(.el-tabs__item.is-active) {
  color: #efffff;
  background: linear-gradient(135deg, rgba(58, 80, 107, 0.9), rgba(91, 192, 190, 0.2));
  box-shadow: 0 12px 24px rgba(2, 6, 23, 0.18);
}

:global(.role-admin) .tabs :deep(.el-tabs__nav-wrap) {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.84), rgba(30, 41, 59, 0.92));
  border: 1px solid rgba(56, 189, 248, 0.14);
  box-shadow: inset 0 1px 0 rgba(34, 211, 238, 0.04);
}

:global(.role-admin) .tabs :deep(.el-tabs__item) {
  color: rgba(216, 240, 255, 0.56);
}

:global(.role-admin) .tabs :deep(.el-tabs__item:hover) {
  color: #eef9ff;
  background: rgba(34, 211, 238, 0.08);
}

:global(.role-admin) .tabs :deep(.el-tabs__item.is-active) {
  color: #f4fbff;
  background: linear-gradient(135deg, rgba(51, 65, 85, 0.94), rgba(56, 189, 248, 0.18));
  box-shadow: 0 12px 24px rgba(2, 6, 23, 0.2);
}

:global(.role-enterprise) .tabs :deep(.el-tabs__nav-wrap) {
  background: linear-gradient(180deg, rgba(246, 251, 248, 0.98), rgba(236, 245, 240, 0.96));
  border: 1px solid rgba(36, 84, 77, 0.1);
}

:global(.role-enterprise) .tabs :deep(.el-tabs__item) {
  color: #6a857f;
}

:global(.role-enterprise) .tabs :deep(.el-tabs__item:hover) {
  color: #24544d;
  background: rgba(216, 239, 227, 0.66);
}

:global(.role-enterprise) .tabs :deep(.el-tabs__item.is-active) {
  color: #16302b;
  background: linear-gradient(135deg, rgba(216, 239, 227, 0.98), rgba(93, 122, 116, 0.14));
  box-shadow: 0 12px 24px rgba(22, 48, 43, 0.08);
}

.stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.row-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 22px;
  font-weight: 700;
  color: var(--surface-text-primary);
}

.title.small-title {
  font-size: 18px;
}

.block-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--surface-title-color);
  margin-bottom: 8px;
}

.resume-item {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--surface-panel-border);
  background: var(--surface-panel-bg);
  color: var(--surface-text-primary);
  cursor: pointer;
}

.resume-item.active,
.resume-item:hover {
  border-color: #7fb2ff;
  box-shadow: 0 12px 30px rgba(15, 98, 254, 0.08);
}

.mini-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.resume-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.detail-header {
  margin-bottom: 8px;
}

.detail-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.score-card {
  padding: 14px;
  border-radius: 16px;
  background: var(--accent-panel-bg);
  border: 1px solid var(--accent-panel-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.score-card span {
  color: var(--surface-text-muted);
}

.score-card strong {
  font-size: 24px;
  color: var(--accent-panel-strong);
}

.info-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

.info-list div {
  padding: 12px;
  border-radius: 14px;
  background: var(--surface-subtle-bg);
  border: 1px solid var(--surface-subtle-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-list span {
  font-size: 12px;
  color: var(--surface-text-muted);
}

.info-list strong {
  font-size: 15px;
  color: var(--surface-text-primary);
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.bullet {
  position: relative;
  padding-left: 16px;
  line-height: 1.8;
  color: var(--surface-text-secondary);
}

.bullet::before {
  content: "";
  position: absolute;
  left: 0;
  top: 11px;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #0f62fe;
}

.bullet.warning::before {
  background: #f97316;
}

.resume-full {
  gap: 12px;
}

.resume-entry {
  padding: 12px;
  border-radius: 14px;
  border: 1px solid var(--surface-subtle-border);
  background: var(--surface-subtle-bg);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.entry-title {
  font-weight: 700;
  color: var(--surface-text-primary);
}

.entry-body {
  color: var(--surface-text-secondary);
  line-height: 1.7;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.preview-image {
  width: 100%;
  min-height: 360px;
  border-radius: 18px;
  background: var(--preview-panel-bg);
  border: 1px solid var(--surface-panel-border);
}

.delivery-account-tip {
  margin: 16px 0;
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--accent-panel-bg);
  border: 1px solid var(--accent-panel-border);
  color: var(--surface-text-secondary);
}

.delivery-dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.delivery-grid {
  display: grid;
  gap: 14px;
  max-height: 68vh;
  overflow: auto;
  padding-right: 4px;
}

.delivery-card {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--surface-panel-border);
  background: var(--surface-panel-bg);
  color: var(--surface-text-primary);
}

.delivery-score {
  font-size: 30px;
  font-weight: 700;
  color: #2563eb;
}

.delivery-company-desc {
  color: var(--surface-text-secondary);
  line-height: 1.8;
  margin: 12px 0;
}

.pre-line {
  white-space: pre-line;
}

.delivery-opening-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.delivery-opening {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--surface-subtle-bg);
  border: 1px solid var(--surface-subtle-border);
  color: var(--surface-text-primary);
}

.delivery-opening-name {
  font-weight: 700;
  color: var(--surface-text-primary);
}

.editor {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--editor-divider);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 1200px) {
  .stat-grid,
  .score-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .grid.two,
  .grid.three {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .stat-grid,
  .score-grid,
  .preview-grid,
  .info-list {
    grid-template-columns: 1fr;
  }

  .row-between {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
